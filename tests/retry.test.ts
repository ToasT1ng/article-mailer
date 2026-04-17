import { describe, it, expect, vi, afterEach } from "vitest";
import { withRetry } from "../src/utils/retry";

afterEach(() => {
  vi.restoreAllMocks();
});

function noDelay() {
  vi.spyOn(global, "setTimeout").mockImplementation((fn: any) => { fn(); return 0 as any; });
}

describe("withRetry", () => {
  it("성공 시 결과를 반환한다", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    expect(await withRetry(fn)).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("첫 번째 실패 후 재시도하여 성공한다", async () => {
    noDelay();
    const fn = vi.fn()
      .mockRejectedValueOnce(new Error("일시 오류"))
      .mockResolvedValue("ok");
    expect(await withRetry(fn)).toBe("ok");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("최대 재시도 횟수 초과 시 마지막 에러를 throw한다", async () => {
    noDelay();
    const fn = vi.fn().mockRejectedValue(new Error("지속 오류"));
    await expect(withRetry(fn, 2)).rejects.toThrow("지속 오류");
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("maxRetries=0 이면 재시도 없이 바로 throw한다", async () => {
    const fn = vi.fn().mockRejectedValue(new Error("즉시 실패"));
    await expect(withRetry(fn, 0)).rejects.toThrow("즉시 실패");
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
