import pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_oral_script import check  # noqa: E402

FX = ROOT / "tests" / "fixtures"
ORAL = (FX / "demo_oral.txt").read_text(encoding="utf-8")
SCRIPT = (FX / "demo_script.md").read_text(encoding="utf-8")


class CheckOralScriptTest(unittest.TestCase):
    def test_demo_passes(self):
        r = check(ORAL, SCRIPT)
        self.assertTrue(r["ok"], r["issues"])
        self.assertGreaterEqual(r["stats"]["keep_ratio"], 0.55)

    def test_rewritten_in_assistant_voice_fails(self):
        r = check(ORAL, "在这个时代，AI 正在赋能每一个职场人的会议效率，让我们一起来看看如何借助智能工具实现待办事项的自动化提取与高效管理。")
        self.assertFalse(r["ok"])
        rules = {i["rule"] for i in r["issues"]}
        self.assertIn("原话保留", rules)
        self.assertIn("句长", rules)
        self.assertIn("AI 腔", rules)

    def test_hedge_and_new_number_flagged(self):
        r = check(ORAL, SCRIPT + "\n效率提升了 80%，以实际为准。")
        self.assertFalse(r["ok"])
        rules = {i["rule"] for i in r["issues"]}
        self.assertIn("规避话术", rules)
        self.assertIn("新增数字", rules)

    def test_markup_is_ignored(self):
        r = check("我试了五天。", "我试了**五天**。 [画面: 日历翻五页] [补:承接]")
        self.assertTrue(r["ok"], r["issues"])


    def test_breath_group_too_long(self):
        r = check("我试了五天", "我试了五天然后发现最难的根本就不是总结而是负责人老是被它搞错")
        self.assertIn("气口", {i["rule"] for i in r["issues"]})

    def test_latin_words_count_as_units(self):
        r = check("Claude Code 和 Codex", "Claude Code 和 Codex 和 OpenCode 和 DeepSeek Harness 和 Hermes 和 OpenClaw 和 WorkBuddy")
        self.assertIn("气口", {i["rule"] for i in r["issues"]})

    def test_expand_mode_declared_numbers_not_flagged(self):
        r = check("本地部署太慢", "本地部署太慢。／一秒只写 **11 个 token**。 [补:数据]", mode="expand")
        self.assertNotIn("新增数字", {i["rule"] for i in r["issues"]})

    def test_expand_mode_requires_tags(self):
        r = check("本地部署太慢", "本地部署太慢，一秒只写十一个字。", mode="expand")
        self.assertIn("扩写标记", {i["rule"] for i in r["issues"]})


    def test_announce_and_preach_flagged(self):
        r = check("我建议用 Mac", "第一个岔口：Windows 还是 Mac？我建议用 Mac。不丢人。")
        rules = {i["rule"] for i in r["issues"]}
        self.assertIn("报幕", rules)
        self.assertIn("说教", rules)


if __name__ == "__main__":
    unittest.main()
