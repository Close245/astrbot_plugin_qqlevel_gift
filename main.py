import json
import time
from datetime import datetime
from typing import Any, Optional

import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import At

# 尝试导入 AiocqhttpMessageEvent（NapCat / OneBot v11 适配器）
try:
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
except ImportError:
    AiocqhttpMessageEvent = None


@register("qqlevel_gift", "PluginDev", "MC 群等级礼包助手", "1.0.0")
class McGiftPlugin(Star):
    """Minecraft 群等级礼包助手

    连接 Minecraft 服务器官网与 QQ 群，基于 QQ 群成员等级自动发放游戏内礼包。
    """

    def __init__(self, context: Context):
        super().__init__(context)
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """插件初始化时创建 aiohttp 会话。"""
        self.session = aiohttp.ClientSession()
        logger.info("[MC Gift] 插件已初始化")

    async def terminate(self):
        """插件卸载时关闭 aiohttp 会话。"""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("[MC Gift] 插件已卸载")

    # ==================== 配置读取 ====================

    def _get_config(self, key: str, default: Any = None) -> Any:
        """读取插件配置，兼容多种可能的配置存储路径。

        AstrBot 会将 _conf_schema.json 中的配置项存入全局配置，
        常见路径为 plugin_configs.{plugin_name}.key 或直接平铺。
        """
        try:
            conf = self.context.get_config()
            if conf is None:
                return default

            if hasattr(conf, "get"):
                # 路径 1：直接平铺
                val = conf.get(key)
                if val is not None:
                    return val

                # 路径 2：plugin_configs > plugin_name
                pc = conf.get("plugin_configs", {})
                if isinstance(pc, dict):
                    pconf = pc.get("qqlevel_gift", {})
                    if isinstance(pconf, dict):
                        val = pconf.get(key)
                        if val is not None:
                            return val

                # 路径 3：plugin_name 平铺
                pconf = conf.get("qqlevel_gift", {})
                if isinstance(pconf, dict):
                    val = pconf.get(key)
                    if val is not None:
                        return val

            return default
        except Exception as e:
            logger.warning(f"[MC Gift] 读取配置项 {key} 失败: {e}")
            return default

    @property
    def _base_url(self) -> str:
        """官网 API 基地址，去除末尾斜杠。"""
        url = self._get_config("website_base_url", "https://your-mc-server.com")
        return url.rstrip("/")

    def _get_gift_config(self) -> list[dict]:
        """获取礼包配置列表，若未配置则返回默认示例。"""
        default = [
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
                "gift_id": "advanced",
                "name": "进阶礼包",
                "min_level": 10,
                "items": [
                    {"id": "minecraft:emerald", "count": 16, "nbt": ""},
                    {"id": "minecraft:experience_bottle", "count": 32, "nbt": ""}
                ],
                "cooldown_days": 0
            }
        ]
        return self._get_config("gift_config", default)

    # ==================== HTTP 请求封装（官网 API） ====================

    async def _http_post(self, path: str, data: dict) -> dict:
        """异步 POST 请求官网 API。"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"{self._base_url}{path}"
        try:
            async with self.session.post(
                url, json=data, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"[MC Gift] 官网 API 请求失败 [{url}]: {e}")
            return {"success": False, "message": "网络请求失败"}
        except Exception as e:
            logger.error(f"[MC Gift] 官网 API 响应解析失败 [{url}]: {e}")
            return {"success": False, "message": "响应解析失败"}

    async def _http_get(self, path: str) -> dict:
        """异步 GET 请求官网 API。"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"{self._base_url}{path}"
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"[MC Gift] 官网 API 请求失败 [{url}]: {e}")
            return {"success": False, "message": "网络请求失败"}
        except Exception as e:
            logger.error(f"[MC Gift] 官网 API 响应解析失败 [{url}]: {e}")
            return {"success": False, "message": "响应解析失败"}

    # ==================== NapCat API 封装 ====================

    async def _call_napcat(self, event: AstrMessageEvent, api_name: str, **payload) -> dict:
        """调用 NapCat（OneBot v11）API。

        仅支持 aiocqhttp 平台（NapCat / go-cqhttp 等）。
        """
        if event.get_platform_name() != "aiocqhttp":
            return {"status": "error", "retcode": -1, "message": "非 aiocqhttp 平台"}

        if AiocqhttpMessageEvent is None:
            return {"status": "error", "retcode": -1, "message": "未导入 AiocqhttpMessageEvent"}

        try:
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            ret = await client.api.call_action(api_name, **payload)
            return ret if isinstance(ret, dict) else {"status": "ok", "data": ret}
        except Exception as e:
            logger.error(f"[MC Gift] NapCat API 调用失败 [{api_name}]: {e}")
            return {"status": "error", "retcode": -1, "message": str(e)}

    async def _get_group_member_info(self, event: AstrMessageEvent, group_id: str, user_id: str) -> Optional[dict]:
        """获取群成员信息，返回 data 字典或 None。"""
        ret = await self._call_napcat(
            event,
            "get_group_member_info",
            group_id=group_id,
            user_id=user_id,
            no_cache=False
        )
        if ret.get("status") == "ok" and ret.get("retcode") == 0:
            return ret.get("data", {})
        return None

    # ==================== 权限判断 ====================

    async def _is_admin(self, event: AstrMessageEvent) -> bool:
        """判断发送者是否为管理员（插件管理员或群管理员/群主）。"""
        qq = event.get_sender_id()

        # 1. 插件管理员列表
        admin_list = self._get_config("admin_qq_list", [])
        if qq in admin_list:
            return True

        # 2. 群管理员 / 群主
        if event.get_platform_name() == "aiocqhttp":
            group_id = event.get_group_id()
            if group_id:
                info = await self._get_group_member_info(event, group_id, qq)
                if info and info.get("role") in ("owner", "admin"):
                    return True

        return False

    # ==================== 官网用户资料查询 ====================

    async def _get_profile_by_qq(self, qq: str) -> Optional[dict]:
        """通过 QQ 号查询官网绑定的游戏账号资料。

        说明：prompt 中原生 API 为 GET /get_profile.php?id={user_id}。
        若官网后端未扩展支持 ?qq= 参数，则需要：
        1. 在本地维护 QQ -> user_id 映射（注册时由其他系统写入，或用户手动绑定）。
        2. 修改服务端增加按 QQ 查询支持。
        本函数优先尝试 ?qq=，失败则尝试本地缓存的 user_id。
        """
        # 优先尝试直接按 QQ 查询（假设官网已扩展支持）
        ret = await self._http_get(f"/php-backend/get_profile.php?qq={qq}")
        if ret.get("success") and ret.get("user"):
            user = ret["user"]
            # 缓存映射以便后续使用 id 查询时也能命中
            await self._cache_qq_userid(qq, user.get("id"))
            return user

        # 回退：使用本地缓存的 user_id
        user_id = await self._get_cached_userid(qq)
        if user_id:
            ret = await self._http_get(f"/php-backend/get_profile.php?id={user_id}")
            if ret.get("success") and ret.get("user"):
                return ret["user"]

        return None

    async def _cache_qq_userid(self, qq: str, user_id: Any):
        """缓存 QQ -> user_id 映射。"""
        try:
            mapping = await self.get_kv_data("qq_userid_map", {})
            mapping[qq] = user_id
            await self.put_kv_data("qq_userid_map", mapping)
        except Exception as e:
            logger.warning(f"[MC Gift] 缓存 QQ 映射失败: {e}")

    async def _get_cached_userid(self, qq: str) -> Optional[str]:
        """从缓存获取 user_id。"""
        try:
            mapping = await self.get_kv_data("qq_userid_map", {})
            return mapping.get(qq)
        except Exception:
            return None

    # ==================== 数据持久化（领取记录） ====================

    async def _get_claims(self) -> dict:
        """获取全部领取记录。结构：{"qq:gift_id": {...}}"""
        return await self.get_kv_data("gift_claims", {})

    async def _save_claim(self, qq: str, gift_id: str, username: str, gift_name: str):
        """写入单条领取记录。"""
        claims = await self._get_claims()
        key = f"{qq}:{gift_id}"
        claims[key] = {
            "qq": qq,
            "gift_id": gift_id,
            "username": username,
            "gift_name": gift_name,
            "claimed_at": int(time.time())
        }
        await self.put_kv_data("gift_claims", claims)

    async def _check_claim_status(self, qq: str, gift_id: str, cooldown_days: int) -> tuple[bool, str]:
        """检查礼包是否可领取。

        Returns:
            (is_blocked, reason_msg)
        """
        claims = await self._get_claims()
        key = f"{qq}:{gift_id}"
        if key not in claims:
            return False, ""

        record = claims[key]
        gift_name = record.get("gift_name", gift_id)

        if cooldown_days == 0:
            return True, f"你已经领取过「{gift_name}」了，该礼包只能领取一次。"

        claimed_at = record.get("claimed_at", 0)
        next_claim = claimed_at + cooldown_days * 86400
        now = int(time.time())
        if now < next_claim:
            remaining = next_claim - now
            days = remaining // 86400
            hours = (remaining % 86400) // 3600
            minutes = (remaining % 3600) // 60
            return True, f"「{gift_name}」领取冷却中，还需 {days}天{hours}小时{minutes}分。"

        return False, ""

    # ==================== 辅助工具方法 ====================

    def _extract_target_qq(self, event: AstrMessageEvent) -> str:
        """从消息链中提取首个 At 的目标 QQ，否则返回发送者 QQ。"""
        messages = event.get_messages()
        for comp in messages:
            if isinstance(comp, At):
                return str(comp.qq)
        return event.get_sender_id()

    def _format_items(self, items: list[dict]) -> str:
        """将物品列表格式化为可读字符串。"""
        parts = []
        for item in items:
            name = item.get("id", "未知物品")
            count = item.get("count", 1)
            parts.append(f"{name} x{count}")
        return "、".join(parts) if parts else "无物品"

    def _match_gifts(self, level: int) -> list[dict]:
        """根据群等级匹配所有满足条件的礼包。"""
        gifts = self._get_gift_config()
        matched = []
        for g in gifts:
            if level >= g.get("min_level", 999):
                matched.append(g)
        return matched

    # ==================== MC 服务端对接（可选/示例） ====================

    async def _give_items_to_player(self, username: str, items: list[dict]) -> bool:
        """向 MC 服务端发送指令给予玩家物品。

        当前为预留对接点，默认仅记录日志并返回 True。
        实际部署时请选择以下一种方案并取消注释：

        方案 A：RCON（推荐，需安装 aiomcrcon）
        -----------------------------------
        from aiomcrcon import Client
        async with Client("127.0.0.1", 25575, "your_rcon_password") as client:
            for item in items:
                item_id = item["id"]
                count = item.get("count", 1)
                nbt = item.get("nbt", "")
                cmd = f'give {username} {item_id}{{{nbt}}} {count}' if nbt else f'give {username} {item_id} {count}'
                resp = await client.send_cmd(cmd)
                logger.info(f"[MC Gift] RCON 响应: {resp}")
        return True

        方案 B：MC 服务端 HTTP API
        -----------------------------------
        url = "http://your-mc-server:8080/api/give_items"
        payload = {"player": username, "items": items}
        async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            result = await resp.json()
            return result.get("success", False)
        """
        logger.info(f"[MC Gift] 物品发放（需对接服务端）: 玩家={username}, 物品={items}")
        return True

    # ==================== 指令实现 ====================

    @filter.command("查等级")
    async def check_level(self, event: AstrMessageEvent):
        """查询 QQ 群等级（支持 @ 他人或查询自己）。"""
        target_qq = self._extract_target_qq(event)
        group_id = event.get_group_id()

        if not group_id:
            yield event.plain_result("该指令只能在群聊中使用。")
            return

        info = await self._get_group_member_info(event, group_id, target_qq)
        if not info:
            yield event.plain_result("无法获取群成员信息，请检查机器人是否为管理员且权限正常。")
            return

        level = info.get("level", "未知")
        nickname = info.get("nickname") or info.get("card") or target_qq
        yield event.plain_result(f"{nickname} 的当前群等级为 Lv.{level}")

    @filter.command("绑定查询")
    async def check_bind(self, event: AstrMessageEvent):
        """查询该 QQ 是否已在官网注册并绑定游戏账号。"""
        target_qq = self._extract_target_qq(event)
        profile = await self._get_profile_by_qq(target_qq)

        if profile:
            username = profile.get("username", "未知")
            email = profile.get("email", "未知")
            is_verified = profile.get("is_verified", 0)
            v_str = "已验证" if is_verified else "未验证"
            role = profile.get("role", "user")
            yield event.plain_result(
                f"✅ QQ {target_qq} 已绑定游戏账号\n"
                f"用户名：{username}\n"
                f"邮箱：{email}\n"
                f"验证状态：{v_str}\n"
                f"角色：{role}"
            )
        else:
            base_url = self._base_url
            yield event.plain_result(
                f"❌ QQ {target_qq} 暂未绑定游戏账号\n"
                f"请前往官网注册并填写 QQ 号：{base_url}"
            )

    @filter.command("领礼包")
    async def claim_gift(self, event: AstrMessageEvent):
        """领取与当前 QQ 群等级匹配的游戏礼包。"""
        async for msg in self._do_claim_gift(event):
            yield msg

    @filter.command("领等级礼包")
    async def claim_gift_alias(self, event: AstrMessageEvent):
        """领取等级礼包（/领礼包 的别名）。"""
        async for msg in self._do_claim_gift(event):
            yield msg

    async def _do_claim_gift(self, event: AstrMessageEvent):
        """礼包领取核心逻辑。"""
        qq = event.get_sender_id()
        group_id = event.get_group_id()

        if not group_id:
            yield event.plain_result("该指令只能在群聊中使用。")
            return

        # 1. 获取群等级
        info = await self._get_group_member_info(event, group_id, qq)
        if not info:
            yield event.plain_result("无法获取群信息，请检查机器人是否为管理员且权限正常。")
            return

        try:
            level = int(info.get("level", 0))
        except (ValueError, TypeError):
            level = 0

        # 2. 查询官网绑定
        profile = await self._get_profile_by_qq(qq)
        if not profile:
            base_url = self._base_url
            yield event.plain_result(
                f"你还未绑定游戏账号，请前往官网注册并填写 QQ 号：{base_url}"
            )
            return

        username = profile.get("username")
        if not username:
            yield event.plain_result("账号信息异常，缺少用户名，请联系管理员。")
            return

        # 3. 匹配礼包
        matched = self._match_gifts(level)
        if not matched:
            yield event.plain_result(f"你当前的群等级为 Lv.{level}，暂无可领取的礼包。")
            return

        success_list = []
        skip_list = []
        fail_list = []

        for gift in matched:
            gift_id = gift.get("gift_id")
            gift_name = gift.get("name", gift_id)
            cooldown = gift.get("cooldown_days", 0)
            items = gift.get("items", [])

            # 4. 检查领取状态
            blocked, reason = await self._check_claim_status(qq, gift_id, cooldown)
            if blocked:
                skip_list.append(f"「{gift_name}」：{reason}")
                continue

            # 5. 发放物品（对接 MC 服务端）
            give_ok = await self._give_items_to_player(username, items)
            if give_ok:
                await self._save_claim(qq, gift_id, username, gift_name)
                success_list.append(f"「{gift_name}」：{self._format_items(items)}")
            else:
                fail_list.append(gift_name)
                logger.error(f"[MC Gift] 发放失败：{gift_name} -> {username}")

        # 6. 组装回复
        lines = []
        if success_list:
            lines.append(f"✅ {username} 领取成功：")
            lines.extend(success_list)

        if skip_list:
            if lines:
                lines.append("")
            lines.append("⏭️ 跳过领取：")
            lines.extend(skip_list)

        if fail_list:
            if lines:
                lines.append("")
            lines.append("⚠️ 以下礼包记录已保存，但物品发放异常，若未到账请联系管理：")
            lines.extend([f"  「{g}」" for g in fail_list])

        if not lines:
            yield event.plain_result(f"你当前的群等级为 Lv.{level}，暂无可领取的礼包。")
            return

        yield event.plain_result("\n".join(lines))

    @filter.command("礼包记录")
    async def gift_record(self, event: AstrMessageEvent):
        """查询某 QQ 的礼包领取记录（管理员指令）。"""
        if not await self._is_admin(event):
            yield event.plain_result("你没有权限使用此指令。")
            return

        target_qq = self._extract_target_qq(event)
        claims = await self._get_claims()

        user_records = [r for r in claims.values() if r.get("qq") == target_qq]
        if not user_records:
            yield event.plain_result(f"QQ {target_qq} 暂无礼包领取记录。")
            return

        lines = [f"📝 QQ {target_qq} 的领取记录："]
        for r in sorted(user_records, key=lambda x: x.get("claimed_at", 0), reverse=True):
            dt = datetime.fromtimestamp(r.get("claimed_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"  • {r.get('gift_name', '未知礼包')}（{dt}）")

        yield event.plain_result("\n".join(lines))

    @filter.command("礼包统计")
    async def gift_stats(self, event: AstrMessageEvent):
        """统计礼包整体领取情况（管理员指令）。"""
        if not await self._is_admin(event):
            yield event.plain_result("你没有权限使用此指令。")
            return

        claims = await self._get_claims()
        if not claims:
            yield event.plain_result("暂无礼包领取记录。")
            return

        counter: dict[str, int] = {}
        qq_set: set[str] = set()
        for r in claims.values():
            name = r.get("gift_name", "未知礼包")
            counter[name] = counter.get(name, 0) + 1
            qq_set.add(r.get("qq", ""))

        lines = ["📊 礼包领取统计："]
        for name, count in sorted(counter.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}：{count} 次")

        lines.append(f"\n总领取记录数：{len(claims)}")
        lines.append(f"独立领取用户数：{len(qq_set)}")

        yield event.plain_result("\n".join(lines))

    @filter.command("重载礼包配置")
    async def reload_gift_config(self, event: AstrMessageEvent):
        """重新加载礼包配置（管理员指令）。"""
        if not await self._is_admin(event):
            yield event.plain_result("你没有权限使用此指令。")
            return

        gifts = self._get_gift_config()
        if not gifts:
            yield event.plain_result("当前没有配置任何礼包，请在 AstrBot WebUI 的插件配置中添加。")
            return

        lines = [f"配置已刷新，当前共 {len(gifts)} 个礼包："]
        for g in gifts:
            lines.append(f"  • {g.get('name', '未命名')}(Lv.{g.get('min_level', 0)}+)")

        yield event.plain_result("\n".join(lines))
