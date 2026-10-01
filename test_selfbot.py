import os
import json
import run

# 1. Test account loading
accs = run.load_accounts()
assert isinstance(accs, list), "Accounts must be a list"
assert len(accs) > 0, "Accounts list should not be empty"

# 2. Test account schema
for a in accs:
    assert "name" in a and a["name"], "Account missing name"
    assert "token" in a and a["token"], "Account missing token"
    assert "guild_id" in a and str(a["guild_id"]).isdigit(), "Account missing/invalid guild_id"
    assert "channel_id" in a and str(a["channel_id"]).isdigit(), "Account missing/invalid channel_id"
    assert isinstance(a.get("self_mute", True), bool), "self_mute must be boolean"
    assert isinstance(a.get("self_deaf", True), bool), "self_deaf must be boolean"
    assert a.get("presence", "online") in ("online", "idle", "dnd", "invisible"), "invalid presence"
    assert isinstance(a.get("enabled", True), bool), "enabled must be boolean"

# 3. Test token masking
masked = run.mask_token("1234567890abcdef")
assert masked == "123456...cdef", f"Unexpected masked token: {masked}"
assert run.mask_token("short") == "***"

# 4. Test settings loading
settings = run.load_settings()
assert "stagger_delay" in settings
assert "max_reconnect_attempts" in settings

# 5. Test bot instantiation
bot = run.VoiceStayBot(accs[0], settings)
assert bot.account_name == accs[0]["name"]
assert bot.guild_id == int(accs[0]["guild_id"])
assert bot.channel_id == int(accs[0]["channel_id"])
assert bot.presence == accs[0].get("presence", "online")
assert bot.target_voice is True

# 6. Test installer module
import install
assert hasattr(install, "install_requirements"), "install.py missing install_requirements function"

print("[OK] Self-check passed: All bot configurations, schema, and classes verified successfully.")
