from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .db import Database

SECTOR_SYSTEM = """你是严谨、克制的中文宏观经济分析师，面向关注中国经济景气度的读者。
你会收到某个板块的官方发布数据表格（总量指标的最新值与近 12 个月历史，以及分类细项的最新值与上期值）。请只依据给定数据解读：
- 数值引用必须与表格一致，不得编造或补充表格之外的数据；
- 材料可能包含分类细项（如 CPI 八大类与食品细项、PPI 生产资料/生活资料与重点行业、工业三大门类与分经济类型、社零商品/餐饮与重点品类、70城分面积段与城市层级、城镇调查失业率的户籍结构/31大城市/工时与PMI从业人员指数、制造业与非制造业PMI分项、进出口环比与累计口径）：解读时应结合细项结构指出主要拉动与拖累项，使结论更具体；
- 材料中可能出现「注：」开头的缺失说明（官方源不可达/未发布的细项），解读时应在相关处如实注明该口径缺失，不得绕过或编造；
- 不预测未来具体数值，只描述现状与方向；
- 提示风险时给出数据依据。
只输出严格 JSON 对象，不要 Markdown：
{"headline":"一句话结论（不超过40字）","points":["3到5条要点，每条不超过80字"],"risks":["0到3条风险提示；没有就给空数组"]}
禁止在 JSON 字符串内使用英文双引号。"""

OVERALL_SYSTEM = """你是严谨、克制的中文宏观经济分析师。你会收到 7 个板块（景气/就业/通胀/消费/房价/工业/进出口）的最新官方数据摘要。
请只依据给定数据做综合研判：
- 数值引用必须与摘要一致，不得编造；
- 不预测未来具体数值；
- 注意各指标数据期不同（部分指标滞后一个月），比较时要注明口径。
只输出严格 JSON 对象，不要 Markdown：
{"headline":"一句话总体判断（不超过40字）","stance":"当前经济景气的整体定位（不超过60字）","signals":["3到5条组合信号"],"risks":["0到3条风险提示；没有就给空数组"],"outlook":"一句话前瞻（不超过60字，不涉及具体数值预测）"}
禁止在 JSON 字符串内使用英文双引号。"""

# 瞬时错误（429/5xx/网络中断）重试一次的退避秒数
_RETRY_BACKOFF_SECONDS = 2.0

# 单次响应体上限：与 SafeFetcher 对齐，防止异常上游返回超大响应耗尽内存。
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class LLMUnavailable(RuntimeError):
    pass


class LLMCallFailed(RuntimeError):
    pass


class LLMAuthError(RuntimeError):
    """鉴权类确定性失败（HTTP 401/403）：重试无效，应熔断整个解读步骤。"""
    pass


class BudgetExceeded(RuntimeError):
    pass


def _clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value or ""))
    return text.strip()[:limit]


def _extract_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text.strip(), re.S)
    if not match:
        raise LLMCallFailed("模型响应中没有 JSON")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        raise LLMCallFailed("模型响应 JSON 解析失败")


class LLMClient:
    """OpenAI 兼容接口的 LLM 客户端，默认 DeepSeek（deepseek-flash，关闭思考模式）。

    每次调用记录真实 usage，月度预算触顶即抛 BudgetExceeded。
    """

    def __init__(self, db: Database, config: Dict[str, Any]):
        self.db = db
        self.config = config
        llm = config.get("llm") or {}
        self.provider = str(llm.get("provider", "deepseek")).lower()
        self.base_url = str(llm.get("base_url", "https://api.deepseek.com")).rstrip("/")
        self.model = str(llm.get("model", "deepseek-flash"))
        env_name = str(llm.get("api_key_env", "DEEPSEEK_API_KEY"))
        self.api_key = str(llm.get("api_key", "")).strip() or os.environ.get(env_name, "")
        self.timeout = int(llm.get("timeout_seconds", 600))
        self.thinking_disabled = bool(llm.get("thinking_disabled", True))
        self.budget = int(llm.get("monthly_token_budget", 200000))

    def _check_budget(self) -> None:
        used = self.db.llm_usage_this_month()
        if used >= self.budget:
            raise BudgetExceeded(
                "本月 LLM 用量已达预算上限（{:,}/{:,} tokens）；可运行 reset-budget 重置后继续"
                .format(used, self.budget)
            )

    def chat(self, system: str, prompt: str, task_type: str) -> str:
        self._check_budget()
        if not self.api_key:
            raise LLMUnavailable(
                "缺少 API Key；请在 local_config.json 配置 llm.api_key 或设置环境变量 {}".format(
                    self.config.get("llm", {}).get("api_key_env", "DEEPSEEK_API_KEY"))
            )
        if self.provider == "mock":
            return self._mock_chat(task_type, prompt)
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        if self.thinking_disabled and self.provider == "deepseek":
            # DeepSeek V4.x 默认开启思考模式（effort=high），必须显式关闭以控制成本。
            # 该字段是 DeepSeek 专有参数，其他 OpenAI 兼容服务可能拒绝，因此按 provider 判断。
            body["thinking"] = {"type": "disabled"}
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "macro-monitor/0.1",
            },
        )
        attempt = 0
        while True:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    # 限量读取：超大响应先拒绝而不是先完整入内存
                    raw = response.read(_MAX_RESPONSE_BYTES + 1)
                    if len(raw or b"") > _MAX_RESPONSE_BYTES:
                        message = "响应体过大（>{:,} 字节），已拒绝".format(
                            _MAX_RESPONSE_BYTES)
                        self.db.record_llm_result("default", task_type, 0, False, message)
                        raise LLMCallFailed(message)
                    value = json.loads(raw.decode("utf-8", errors="replace"))
                break
            except urllib.error.HTTPError as exc:
                message = "HTTP {}: {}".format(
                    exc.code, exc.read(4096).decode("utf-8", errors="replace")[:300])
                if exc.code in (401, 403):
                    # 鉴权失败是确定性错误：重试无效，抛 LLMAuthError 供上层熔断
                    self.db.record_llm_result("default", task_type, 0, False, message)
                    raise LLMAuthError(message)
                if (exc.code == 429 or exc.code >= 500) and attempt < 1:
                    # 瞬时错误：重试一次并退避
                    attempt += 1
                    self.db.record_llm_result("default", task_type, 0, False, message)
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                self.db.record_llm_result("default", task_type, 0, False, message)
                raise LLMCallFailed(message)
            except urllib.error.URLError as exc:
                message = "网络错误：{}".format(exc.reason)
                if attempt < 1:
                    attempt += 1
                    self.db.record_llm_result("default", task_type, 0, False, message)
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                self.db.record_llm_result("default", task_type, 0, False, message)
                raise LLMCallFailed(message)
            except json.JSONDecodeError as exc:
                message = "响应不是合法 JSON：{}".format(exc)[:300]
                self.db.record_llm_result("default", task_type, 0, False, message)
                raise LLMCallFailed(message)
        output = str(value.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not output:
            message = "模型返回了空内容"
            self.db.record_llm_result("default", task_type, 0, False, message)
            raise LLMCallFailed(message)
        usage = value.get("usage") or {}
        units = int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
        if units == 0:
            units = int(len(system + prompt) * 0.3 + len(output) * 0.6)  # 本地估算兜底
        self.db.record_llm_result("default", task_type, units, True)
        return output

    @staticmethod
    def _mock_chat(task_type: str, prompt: str) -> str:
        if task_type == "sector":
            return json.dumps({
                "headline": "板块解读（mock）",
                "points": ["要点一", "要点二", "要点三"],
                "risks": ["风险提示（mock）"],
            }, ensure_ascii=False)
        return json.dumps({
            "headline": "总体判断（mock）",
            "stance": "景气定位（mock）",
            "signals": ["组合信号一", "组合信号二"],
            "risks": ["风险提示（mock）"],
            "outlook": "前瞻（mock）",
        }, ensure_ascii=False)

    # ---------- 业务方法 ----------

    def _chat_json(self, system: str, prompt: str, task_type: str) -> Dict[str, Any]:
        """调用 chat 并解析 JSON；模型偶发返回非 JSON/畸形 JSON 时重试一次。"""
        output = self.chat(system, prompt, task_type)
        try:
            return _extract_json(output)
        except LLMCallFailed:
            output = self.chat(system, prompt, task_type)
            return _extract_json(output)

    @staticmethod
    def _normalize_list(value: Any, limit: int, per_item: int) -> List[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item, per_item) for item in value[:limit]]

    def interpret_sector(self, sector_name: str, material: str) -> Dict[str, Any]:
        # system 提示词已在 messages 中单独携带，user 消息只放板块素材，避免重复计费
        prompt = "=== 板块：{} ===\n{}".format(sector_name, material)
        value = self._chat_json(SECTOR_SYSTEM, prompt, "sector")
        return {
            "headline": _clean_text(value.get("headline"), 80),
            "points": self._normalize_list(value.get("points"), 5, 160),
            "risks": self._normalize_list(value.get("risks"), 3, 160),
            "model": self.model,
        }

    def interpret_overall(self, material: str) -> Dict[str, Any]:
        # system 提示词已在 messages 中单独携带，user 消息只放数据摘要
        prompt = "=== 各板块数据摘要 ===\n" + material
        value = self._chat_json(OVERALL_SYSTEM, prompt, "overall")
        return {
            "headline": _clean_text(value.get("headline"), 80),
            "stance": _clean_text(value.get("stance"), 160),
            "signals": self._normalize_list(value.get("signals"), 5, 160),
            "risks": self._normalize_list(value.get("risks"), 3, 160),
            "outlook": _clean_text(value.get("outlook"), 160),
            "model": self.model,
        }
