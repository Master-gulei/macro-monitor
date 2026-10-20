# 📈 macro-monitor · 宏观经济主要指标月度看板

> 每月自动抓取官方宏观经济数据（PMI、CPI/PPI、社零、70 城房价、工业、进出口、就业），
> 由 AI 生成板块解读与综合研判，输出**单文件 HTML 看板**（黑底暗色主题、立体感表格全屏铺满，
> ECharts 图表 + 表格降级）。

**🐍 纯 Python 标准库** · **🗄️ SQLite 本地库** · **🤖 DeepSeek AI 解读** · **📄 单文件 HTML 看板** · **💸 月度 token 预算滚动（默认 200K/月）**

- 📡 **数据源**：官方免费公开接口为主、多源兜底（国家统计局 easyquery / 官网新闻稿 / 国民经济运行情况稿、海关总署统计快讯、人力资源社会保障部、东方财富数据中心）
- 🤖 **AI**：DeepSeek（deepseek-flash，关闭思考模式），月度 token 预算锚点滚动（默认 200K/月）
- 🖥️ **运行环境**：纯 Python 标准库，本地 Python 3.11，无第三方依赖

## 🚀 快速开始

1. 🔑 **配置 API Key**（二选一）
   - 在项目根目录新建 `local_config.json`（已 gitignore）：
     ```json
     {"llm": {"api_key": "sk-你的密钥"}}
     ```
   - 或设置环境变量 `DEEPSEEK_API_KEY`
2. 🔍 **（可选）先校验配置**（不访问网络、不调用 LLM）：
   ```bat
   run.bat run --dry-run
   ```
3. ▶️ **运行**（Windows 双击 `run.bat`，Linux/macOS 用 `./run.sh run`）：
   ```bat
   run.bat run
   ```
   输出：`out\宏观监测-YYYY-MM-DD.html`，浏览器直接打开。
4. ✅ **检查结果**：每次运行后的 JSON 结果包含 `fetch`（抓取）、`interpret`（AI 解读）、`report`（看板）三段状态。

Linux/macOS 可用 crontab 定时运行（`crontab -e` 添加，每 10 天一次）：
```cron
30 8 1,10,20 * * cd /path/to/macro-monitor && ./run.sh run >> data/cron.log 2>&1
```

## 📋 CLI 命令

| 命令 | 说明 |
|---|---|
| `run.bat run` | 完整月度流水线：抓取 → 房价聚合 → AI 解读 → 看板 |
| `run.bat run --force` | 忽略"本月已抓取"标记，强制重新抓取 |
| `run.bat run --refresh-ai` | 强制重新生成 AI 解读 |
| `run.bat run --no-ai` | 只抓数据、出看板，跳过 AI |
| `run.bat run --dry-run` | 仅校验配置与状态，不访问网络与 LLM |
| `run.bat report` | 不抓取，仅用库内数据重新生成看板（加 `--refresh-ai` 可顺带重新解读） |
| `run.bat status` | 查看数据量、LLM 预算、逐指标新鲜度、数据告警与最近同步（Linux 用 `./run.sh status`） |
| `run.bat reset-budget` | 手动重置本月 LLM token 计数 |
| `run.bat prune --days 90` | 清理过期的审计/告警/用量/同步记录（默认保留 90 天） |

> 说明：抓取与解读均按自然月去重（幂等），重复运行不会重复消费；数据按
> `(指标, 数据期, kind, 城市)` 覆盖更新。预算在跨月时自动前滚，一般无需 reset-budget。

## 🧭 看板内容

1. 🚦 **景气总览红绿灯**：11 个指标的最新值与信号，信号依据明确较上期上升/下降方向与幅度（阈值为经验性设定，以 AI 解读为准）；缺失指标红色"数据缺失"标注，越界数据顶部横幅告警
2. 🤖 **AI 重点解读**：综合研判 + 7 板块（景气/就业/通胀/消费/房价/工业/进出口）解读与风险提示；缺失口径（如分年龄组失业率、分贸易方式进出口、人社部新增就业）在素材与解读中如实注明
3. 📈 **趋势图**：近 24 个月走势（ECharts CDN，加载失败自动降级为表格）
4. 🏠 **70 城房价专项**：上涨城市数、分线均值、领涨领跌前五、70 城完整明细（新建/二手）
5. 📅 **数据日历**：最新数据期、较上期变化、来源、预计下期发布日；抓取失败的指标标注"数据缺失"
6. 📚 **数据源清单附录**：各指标官方发布渠道与本项目接入的免费来源

## 📁 项目结构

```
macro-monitor/
├── src/macro_monitor/       # cli、config、db、fetch、indicators、ai、pipeline、report
│   └── sources/             # __init__.py（HtmlSource 基类）、html_parser.py（通用表格解析）、
│                            # nbs.py（easyquery）、statsweb.py（列表页定位，指标解析拆分至
│                            # statsweb_house/profit/news/unemp/pmi.py Mixin + statsweb_patterns.py 共享正则）、
│                            # eastmoney.py（数据中心兜底）、customs.py（海关总署）、mohrss.py（人社部）
├── config.json              # 公开配置（数据源、预算、安全白名单、out/ 保留份数）
├── run.bat                  # Windows 入口（chcp 65001 + PYTHONPATH）
├── run.sh                   # Linux/macOS 入口（bash + PYTHONPATH）
├── README.md / DESIGN.md    # 使用说明 / 设计文档（含官方数据源清单）
└── 仅本地目录（已被 .gitignore 排除，不入仓库）：
    ├── tests/ + fixtures/   # 离线单测（纯标准库 unittest）
    ├── run_tests.py         # 测试入口
    ├── data/                # macro.db（SQLite）、macro.db.bak（自动备份）、network.lock
    ├── out/                 # 生成的 HTML 看板（仅保留最近 keep_reports 份）
    └── local_config.json    # 本地密钥（gitignored）
```

## 🧪 单元测试

测试代码仅保留在作者本地（仓库只包含核心源码，`tests/`、`run_tests.py` 已被 .gitignore 排除）：

```bat
set PYTHONPATH=%CD%\src
python run_tests.py
```

全部用例离线运行（fixtures 为各数据源的响应样本），不访问网络与 LLM。

## 🛡️ 稳定性与风险控制

| 机制 | 说明 |
|---|---|
| 数据合理性校验 | 每行入库前按指标口径做合理区间校验；越界值照常入库但写入 `data_warnings` 告警表，`status` 输出告警数量与最近 10 条明细、看板顶部横幅展示（防范历史上 CPI 环比错误静默入库 12 个月这类问题） |
| LLM 熔断 | 鉴权/预算异常（401/403/超额）立即熔断；其他失败连续 3 次自动熔断跳过剩余板块，避免坏响应烧完预算 |
| LLM 响应上限 | 单次响应体上限 10 MB，超限直接拒绝且不计入预算（失败审计留痕） |
| LLM base_url 白名单 | `llm.allowed_hosts` 校验 base_url 主机（LLM 请求不走抓取器安全白名单，需单独约束） |
| 看板脚本安全 | ECharts 通过 jsdelivr 加载并附 sha384 SRI 完整性校验；CDN 不可用自动切换 unpkg 备用（同一构建同一哈希），均不可用时降级为静态表格 |
| 数据库备份 | 抓取到新数据后自动用 SQLite 在线备份 API 快照到 `data/macro.db.bak`（WAL 模式安全） |
| 审计清理 | `run.bat prune` 清理过期的审计/告警/用量/同步记录（默认保留 90 天），防止审计表无限增长 |
| 看板保留 | `out/` 仅保留最近 `site.keep_reports`（默认 6）份看板，按文件修改时间清理 |
| 失败隔离 | 看板生成失败不影响已完成的抓取/解读结果；单一指标/数据源失败不影响其他指标（多源兜底） |
| 月度幂等 | 抓取与解读按自然月去重，重复运行不重复消费；预算跨月自动前滚 |

## ✅ 验证状态（最近一次真实运行）

- 🧪 单测：160/160 通过（含本次新增：数据合理性校验告警、LLM 熔断、失败隔离、响应大小上限、SRI/备用 CDN、base_url 白名单、批写入去重、备份、新鲜度、缺数高亮、告警去重、年度失业率稿匹配、审计清理 prune、未闭合 script 恢复重解析、raw_decode JSON 提取、local_config 非对象校验等）
- 📡 指标覆盖率：9/11（城镇新增就业因人社部官网动态渲染+反爬未获取、出口价格指数因海关页面 502 未获取，看板与 AI 素材均已注明缺失）
- 🤖 AI 解读：8/8 段齐备（7 板块 + 综合研判）；LLM 用量 70,128 / 200,000 tokens（2026-10）
- 🔬 分类细项：CPI 八大类/食品细项 20 项、PPI 生产资料链/重点行业 19 项、
  工业增加值门类与经济类型 9 项、工业企业利润分类型/分行业 11 项、
  社零城乡/商品/餐饮/重点品类 9 项、70 城分面积段全国均值 12 项、
  PMI 制造业/非制造业分项 23 项、进出口环比/累计额/累计同比 6 项、
  失业率户籍结构/31 城/工时 7 项，
  均由统计局官网月度报告新闻稿解析入库，AI 解读结合细项结构指出主要拉动与拖累项。

详细设计、指标注册表与数据源对比见 [DESIGN.md](DESIGN.md)。
