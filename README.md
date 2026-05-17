# MC 群等级礼包助手

一个 AstrBot 插件，用于连接 Minecraft 服务器官网与 QQ 群，实现基于 **QQ 群成员等级** 自动发放游戏内礼包的功能。

---

## 📌 项目关系说明

本项目是 **[ServerManager](https://github.com/Close245/ServerManager)** 的**从属插件**（子项目/客户端插件）。

- **主项目**：[Close245/ServerManager](https://github.com/Close245/ServerManager) —— 负责 Minecraft 服务端的综合管理，包含 Java Spigot 插件 `WebsiteAuth` 与 PHP 官网后端用户系统。
- **本项目（从项目）**：`astrbot_plugin_qqlevel_gift` —— 作为 AstrBot 的 Python 插件，提供 QQ 群内的等级查询、账号绑定查询、礼包领取等交互能力，与主项目的 PHP 后端 API 对接。

> 单独安装本插件无法独立完成全部功能，需配合主项目的 `WebsiteAuth` 插件及 PHP 后端使用。

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **群等级查询** | `/查等级 [@某人]` —— 实时查询 QQ 群成员等级 |
| **绑定查询** | `/绑定查询 [@某人]` —— 查询 QQ 是否已绑定官网游戏账号 |
| **等级礼包领取** | `/领礼包` / `/领等级礼包` —— 按群等级匹配并发放对应礼包 |
| **领取记录** | `/礼包记录 [@某人]` —— 查看历史领取记录（管理员） |
| **领取统计** | `/礼包统计` —— 统计各礼包领取情况（管理员） |
| **配置重载** | `/重载礼包配置` —— 刷新礼包配置（管理员） |

- 礼包支持 **一次性** 与 **周期性冷却** 两种模式
- 物品发放预留 **RCON** / **HTTP API** 两种 MC 服务端对接方案
- 支持通过 AstrBot WebUI 可视化配置礼包内容

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 机器人框架 | [AstrBot](https://github.com/AstrBot/AstrBot)（Python 插件体系） |
| QQ 协议端 | NapCat（OneBot v11 反向 WebSocket） |
| MC 服务端 | Java Spigot + `WebsiteAuth` 插件 |
| 官网后端 | PHP 用户系统 API（由主项目提供） |
| 网络请求 | `aiohttp`（全异步，禁止同步阻塞） |

---

## 📦 安装方法

### 1. 前置依赖

- 已部署并运行 [AstrBot](https://github.com/AstrBot/AstrBot)
- 已配置 NapCat（aiocqhttp）适配器，且机器人在目标 QQ 群拥有 **管理员** 权限
- 已部署主项目 [ServerManager](https://github.com/Close245/ServerManager) 的 PHP 后端与 `WebsiteAuth` 插件

### 2. 安装插件

**方式一：通过 AstrBot 插件市场（推荐）**

在 AstrBot 控制台或 WebUI 的插件市场中搜索 `qqlevel_gift` 并安装。

**方式二：手动安装**

```bash
# 进入 AstrBot 插件目录
cd AstrBot/data/plugins

# 克隆本仓库
git clone https://github.com/your-repo/astrbot_plugin_qqlevel_gift.git

# 重启 AstrBot
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
# 或
pip install aiohttp
```

---

## ⚙️ 配置说明

在 AstrBot WebUI → **插件配置** → **MC 群等级礼包助手** 中进行配置，对应 `_conf_schema.json` 定义：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `website_base_url` | string | MC 服务器官网 API 基地址，如 `https://mc.example.com` |
| `admin_qq_list` | list | 插件管理员 QQ 号列表（拥有管理员指令权限） |
| `gift_config` | list | 礼包配置数组，详见下方示例 |

### 礼包配置示例

```json
[
  {
    "gift_id": "newbie",
    "name": "新手礼包",
    "min_level": 5,
    "items": [
      {"id": "minecraft:diamond", "count": 5, "nbt": ""},
      {"id": "minecraft:iron_ingot", "count": 16, "nbt": ""}
    ],
    "cooldown_days": 0
  },
  {
    "gift_id": "weekly",
    "name": "周常礼包",
    "min_level": 8,
    "items": [
      {"id": "minecraft:emerald", "count": 8, "nbt": ""}
    ],
    "cooldown_days": 7
  }
]
```

- `gift_id`：礼包唯一标识
- `min_level`：最低群等级要求
- `items`：MC 物品列表（`id` + `count` + `nbt`）
- `cooldown_days`：领取冷却天数，`0` 表示 **一次性礼包**

---

## 📝 指令列表

### 普通群员指令

| 指令 | 用法 | 说明 |
|------|------|------|
| `查等级` | `/查等级` 或 `/查等级 @某人` | 查询群等级 |
| `绑定查询` | `/绑定查询` 或 `/绑定查询 @某人` | 查询官网账号绑定状态 |
| `领礼包` | `/领礼包` | 按当前群等级领取可匹配的礼包 |
| `领等级礼包` | `/领等级礼包` | `/领礼包` 的别名 |

### 管理员指令

| 指令 | 用法 | 说明 |
|------|------|------|
| `礼包记录` | `/礼包记录` 或 `/礼包记录 @某人` | 查询礼包领取历史 |
| `礼包统计` | `/礼包统计` | 查看全服礼包领取统计 |
| `重载礼包配置` | `/重载礼包配置` | 刷新内存中的礼包配置 |

> 管理员判定：插件配置中的 `admin_qq_list` **或** QQ 群管理员/群主。

---

## 🔗 数据流

```
QQ 群用户发送指令
    ↓
AstrBot 插件接收事件 (AstrMessageEvent)
    ↓
提取 QQ 号、群号
    ↓
调用 NapCat API (get_group_member_info) → 获取群等级 level
    ↓
调用官网 API (get_profile.php) → 获取绑定的游戏账号 username
    ↓
查询本地礼包配置与领取记录（KV 存储）
    ↓
判断是否满足领取条件
    ↓
[满足] 更新领取记录 → 通知 QQ 群 → (可选) 通知 MC 服务端给予物品
[不满足] 返回原因（等级不足 / 未绑定 / 已领取 / 冷却中）
```

---

## 🎮 MC 服务端对接

本插件默认 **不直接操作 MC 服务端**，仅在日志中记录应发放的物品。如需自动发放，请修改 `main.py` 中 `_give_items_to_player` 方法，选择以下任一方案：

### 方案一：RCON（推荐）

```python
from aiomcrcon import Client
async with Client("127.0.0.1", 25575, "your_rcon_password") as client:
    resp = await client.send_cmd(f"give {username} minecraft:diamond 5")
```

### 方案二：HTTP API

通过主项目或第三方插件暴露 HTTP 接口，异步 POST 物品列表。

---

## ⚠️ 注意事项

1. **机器人权限**：机器人必须在目标 QQ 群拥有 **管理员** 权限，否则无法调用 `get_group_member_info` 获取群等级。
2. **官网 API 扩展**：`get_profile.php` 默认按 `id` 查询。本插件优先尝试 `?qq=` 参数查询；若服务端未支持，需本地维护 QQ → user_id 映射。
3. **异步规范**：插件内所有网络请求均使用 `aiohttp`，禁止引入 `requests` 等同步库。
4. **依赖主项目**：本插件必须与 [ServerManager](https://github.com/Close245/ServerManager) 的 PHP 后端配合使用。

---

## 📄 许可证

本项目采用与主项目一致的许可证，详见 [LICENSE](./LICENSE)。

---

## 🤝 相关项目

- **主项目（服务端管理）**：https://github.com/Close245/ServerManager
- **机器人框架**：https://github.com/AstrBot/AstrBot
- **QQ 协议端**：https://github.com/NapNeko/NapCatQQ
