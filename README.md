# 家常菜单 HomeCook

一套面向中式家庭饮食的菜单管理应用，参照 Mealie 的思路但针对国内习惯重写：
中式食材分类、家常菜谱结构、本地单位（斤/两/克/汤匙）与采购方式（菜市场/超市/电商/社区团购）。

## 仓库与镜像

- 源码仓库：https://github.com/mjy378283319/homecook
- 容器镜像：`ghcr.io/mjy378283319/homecook:latest`（多架构 amd64 / arm64，push 后由 GitHub Actions 自动构建）
- 与 `xcf2mealie_web` **完全独立**：HomeCook 自带下厨房导入，不依赖 Mealie。

## 与 Mealie 的差异（本地化重点）

| 维度 | Mealie（国外习惯） | HomeCook（本地化） |
|------|-------------------|-------------------|
| 食材分类 | 通用 pantry 标签 | 中式分类树：蔬菜/肉禽蛋/水产/主食杂粮/豆制品/调料干货… |
| 单位 | cup/oz/g 为主 | 斤、两、克、公斤、汤匙、茶匙、个、瓣、适量、少许… |
| 采购 | 单一清单 | 按食材分类 + 渠道（菜市场/超市/电商）分组，本地单位聚合 |
| 菜谱结构 | 步骤 + 食材 | 额外支持菜系、做法、口味标签、准备/烹饪时长、整体小贴士 |
| 导入 | 多国站点 | 下厨房（xiachufang.com）尽力解析，导入前可复核编辑 |

## 功能模块

1. **菜谱管理**：菜系/做法/难度/人份/时长/口味标签/小贴士；食材明细（本地单位）；分步做法（每步可带提示）。
2. **食材库**：中式分类树 + 别名字典；记录默认单位、采购规格、常去渠道。
3. **采购清单**：从勾选菜谱或周菜单一键聚合；按名称合并、按斤两/毫升换算展示；可勾选已购、填采购渠道。
4. **周菜单**：一周早/午/晚排菜，按区间生成采购清单。
5. **单位换算**：斤↔两↔克、升↔毫升、汤匙↔茶匙，以及定性单位（适量/少许）。
6. **导入**：粘贴下厨房链接，尽力解析用料与步骤后进入可编辑表单。
7. **鉴权**：独立登录页（支持 Bitwarden 自动填充），写入 httpOnly 会话 Cookie；读操作开放，写操作需登录。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：原生 JS 单页应用（无构建步骤，可离线运行）
- 部署：Docker / docker-compose，数据持久化于 `/data` 卷

## 数据模型（核心表）

- `users` 账号
- `categories` 食材分类树（parent_id 自引用）
- `ingredients` 食材（关联分类、别名、默认单位、采购规格、渠道）
- `recipes` 菜谱（菜系/做法/难度/时长/口味/小贴士/来源）
- `recipe_ingredients` 菜谱食材（数量、单位、备注，可关联食材或自由文本）
- `recipe_steps` 步骤（序号、标题、正文、提示）
- `meal_plans` 周菜单（日期、餐别、菜谱）
- `shopping_lists` / `shopping_items` 采购清单及条目

## 本地运行（开发）

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
set DB_PATH=%CD%/data/homecook.db
uvicorn app.main:app --reload --port 8000
# 浏览器打开 http://localhost:8000
```

默认账号：`WEB_USER` / `WEB_PASSWORD`（未设置时默认 `admin` / `homecook`）。

## Docker 部署

```bash
docker compose up -d        # 直接从 ghcr 拉取镜像
# 访问 http://<主机IP>:9926
```

本地开发构建（改代码后）：

```bash
docker build -t ghcr.io/mjy378283319/homecook:latest .
docker compose up -d
```

> ⚠️ 部署前务必修改 `WEB_PASSWORD` 与 `SECRET_KEY`，不要把默认口令暴露到公网。
> `SECRET_KEY` 可用 `openssl rand -hex 32` 生成。

环境变量：

| 变量 | 说明 | 默认 |
|------|------|------|
| `WEB_USER` | 登录用户名 | admin |
| `WEB_PASSWORD` | 登录密码 | homecook |
| `SECRET_KEY` | 会话签名密钥（务必修改） | 开发占位值 |
| `DB_PATH` | SQLite 路径（容器内） | /data/homecook.db |
| `TZ` | 时区 | Asia/Shanghai |

## Unraid 部署

1. 将 `homecook.xml` 放到 Unraid 的 `templates-user` 目录，或在 CA 中「从模板路径添加」。
2. 模板会自动拉取 `ghcr.io/mjy378283319/homecook:latest`，映射端口 9926，映射 `/data` 到 `/mnt/user/appdata/homecook`。
3. 修改 `WEB_PASSWORD` 与 `SECRET_KEY` 后启动。

## 导入说明

下厨房解析为「尽力而为」：优先抓取移动版页面，失败回退桌面版。
因页面结构可能变动，解析结果请务必在表单中复核后再保存。
如解析不理想，可直接用「新建菜谱」手动录入。
