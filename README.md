# 可转债退市 / 强赎数据分析（Redeem）

从集思录抓取**已退市可转债**数据，补充强赎时间与价格，并做退市统计与「存续年限 → 强赎概率」的贝叶斯建模分析。

## 目录结构

```
Redeem/
├── crawler.py          # ① 抓取集思录退市转债 → *_in.xlsx
├── augment.py          # ② 补充强赎时间 / 强赎价格 → *_au.xlsx
├── redeem.py           # ③ 退市统计 → *_last.xlsx / *_small.xlsx
├── bayestime.py        # ④ 贝叶斯逻辑回归（存续年限→强赎概率）→ bayes.png / *_bayes.xlsx
├── jisilu_config.json  # 集思录账号配置（crawler 登录用）
├── bayestime_config.json  # 贝叶斯采样参数配置
└── README.md
```

## 数据流

```
crawler.py  ──▶ 2026_08_14_in.xlsx ──┬─▶ augment.py ──▶ 2026_08_14_au.xlsx ──▶ redeem.py ──▶ *_last.xlsx / *_small.xlsx
                                     └─▶ bayestime.py ──▶ bayes.png / 2026_08_14_bayes.xlsx
```

## 环境依赖

- Python 虚拟环境：`/opt/finance_env/venv`（下面命令用 `/opt/finance_env/venv/bin/python`）
- 依赖：`selenium`、`pandas`、`openpyxl`、`requests`、`cryptography`、`pymc3`、`arviz`、`numpy`、`bs4`、`lxml`
  - `augment.py` 额外需要 `webdriver-manager`（或本地 `chromedriver`）
- 浏览器：Chrome + 匹配的 `chromedriver`（本机：Chrome 146，chromedriver 位于 `~/.local/bin/chromedriver`）
- 中文字体：`Noto Sans CJK SC`（位于 `~/.fonts/`，供 matplotlib 绘图使用）

## 使用步骤

所有脚本需在 `/opt/Redeem` 目录下运行，文件按顺序流转。

### ① 抓取退市转债（crawler.py）

```bash
cd /opt/Redeem
/opt/finance_env/venv/bin/python crawler.py
```

- 自动登录集思录（`requests + AES` 程序化登录，账号取自 `jisilu_config.json`，登录态缓存于 `~/.jisilu_cookies.pkl`，失效自动重登），无需手动登录
- 输出：`YYYY_MM_DD_in.xlsx`（sheet: `jsl`），列含：`代码 / 名称 / 最后交易价格 / 最低收盘价格 / 最高收盘价格 / 正股代码 / 正股名称 / 发行规模 / 回售规模 / 剩余规模 / 发行日期 / 最后交易日 / 到期日期 / 存续年限 / 退市原因`

### ② 补充强赎时间 / 价格（augment.py）

```bash
/opt/finance_env/venv/bin/python augment.py 2026_08_14_in.xlsx
```

- 对 `退市原因 == "强赎"` 的转债，逐个打开集思录详情页，在公告栏中匹配标题按顺序包含「提前、赎回、名称、公告」且不含「不提前」的公告（或「提前、赎回、法律意见」），取**最早一条**作为强赎日期；再在历史行情中定位该日期的收盘价作为强赎价格（无精确匹配时回退到最近前一交易日）
- 输出：`2026_08_14_au.xlsx`，新增列 `强赎时间 / 强赎价格`
- 浏览器/登录方式与 crawler.py 一致：复用其 `get_browser`（本地 chromedriver + 反检测 + 集思录登录 cookie 注入），无需手动准备 driver

### ③ 退市统计（redeem.py）

```bash
/opt/finance_env/venv/bin/python redeem.py 2026_08_14_au.xlsx
```

- 统计：全局强赎比例、近两年（最后交易日在近 730 天内）强赎比例
- 分布：强赎 / 非强赎条件下的存续年限分布（各分位数）、发行规模 ≤ 5 亿转债的强赎价格分布
- 输出：`2026_08_14_last.xlsx`（近两年已退市转债）、`2026_08_14_small.xlsx`（小规模已退市转债）

### ④ 贝叶斯分析（bayestime.py）

```bash
/opt/finance_env/venv/bin/python bayestime.py 2026_08_14_in.xlsx
```

- 对「存续年限 → 是否强赎」建立贝叶斯逻辑回归（PyMC3，Bernoulli 似然），采样 2000 后验样本
- 输出：
  - `bayes.png`：不同存续年限下强赎后验概率分布（中位数 + 95% 区间带）
  - `YYYY_MM_DD_bayes.xlsx`：存续年限 0.6~6.0 年、每 0.1 年一行的强赎后验概率中位数表（`存续年限` 列固定显示 1 位小数）
- **快速验证**：MCMC 采样较慢，可将 `bayestime_config.json` 中的 `draws` / `tune` 调小（如 100/100），几十秒即可跑通；出正式结果时改回 2000/1000

## 配置文件

### jisilu_config.json（crawler 登录用）

```json
{
  "username": "手机号",
  "password": "密码"
}
```

### bayestime_config.json（采样参数）

```json
{
  "draws": 2000,
  "tune": 1000,
  "chains": 2,
  "random_seed": 42
}
```

`random_seed` 保证结果可复现。

## 输出文件汇总

| 脚本 | 输入 | 输出 |
|---|---|---|
| crawler.py | 无 | `YYYY_MM_DD_in.xlsx` |
| augment.py | `*_in.xlsx` | `*_au.xlsx`（新增 强赎时间/强赎价格） |
| redeem.py | `*_au.xlsx` | `*_last.xlsx`、`*_small.xlsx` |
| bayestime.py | `*_in.xlsx` | `bayes.png`、`YYYY_MM_DD_bayes.xlsx` |

## 说明

- 集思录登录逻辑原在 `harpoon.py` 中，已并入 `crawler.py`，`harpoon.py` 已删除
- 中文字体在 Linux 上使用 `Noto Sans CJK SC`（`Microsoft YaHei` 仅适用于 Windows）
