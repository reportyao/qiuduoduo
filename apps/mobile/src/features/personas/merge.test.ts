import { describe, expect, it } from "vitest";
import type { PersonaCopy, PersonaMeta } from "./personas";
import { mergePersonaContent, type PersonaConfigResponse } from "./merge";

const baseMeta = {
  id: "laopao",
  name: "感性老炮",
  tag: "兄弟 · 幽默 · 有情绪",
  address: "兄弟",
  sample: "sample",
  avatar: 0,
} as PersonaMeta;

const baseCopy = {
  brandSub: "fallback brand",
  saleTitle: "fallback sale",
  emptyTitle: "fallback empty",
  restTitle: "fallback rest",
} as unknown as PersonaCopy;

const config: PersonaConfigResponse = {
  version: 3,
  profiles: [
    { id: "zhuanjia", name: "理性专家", address: "你", tone: "冷静" },
    { id: "laopao", name: "老炮", address: "老铁", tone: "兄弟 · 幽默" },
    { id: "meng", name: "元气搭子", address: "你", tone: "活泼" },
  ],
  slots: [
    { persona_id: "laopao", slot_key: "brandSub", template: "老炮坐镇" },
    { persona_id: "laopao", slot_key: "emptyTitle", template: "{address}，今晚没货" },
    { persona_id: "zhuanjia", slot_key: "brandSub", template: "专家坐镇" },
  ],
};

describe("mergePersonaContent", () => {
  it("没有配置时完全回退 bundled COPY", () => {
    const { meta, copy } = mergePersonaContent("laopao", null, baseMeta, baseCopy);
    expect(meta).toEqual(baseMeta);
    expect(copy).toEqual(baseCopy);
  });

  it("后台 profile 覆盖名称/地址/语气，slot 覆盖文案并替换 address", () => {
    const { meta, copy } = mergePersonaContent("laopao", config, baseMeta, baseCopy);
    expect(meta.name).toBe("老炮");
    expect(meta.address).toBe("老铁");
    expect(copy.brandSub).toBe("老炮坐镇");
    expect(copy.emptyTitle).toBe("老铁，今晚没货");
    expect(copy.restTitle).toBe("fallback rest");
  });

  it("只改当前人设，不影响其他角色", () => {
    const { copy } = mergePersonaContent("zhuanjia", config, baseMeta, baseCopy);
    expect(copy.brandSub).toBe("专家坐镇");
    expect(copy.emptyTitle).toBe("fallback empty");
  });
});
