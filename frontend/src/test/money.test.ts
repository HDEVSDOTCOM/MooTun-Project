import { describe, expect, it } from "vitest";
import { baht, calendarDate, isNegative, monthLabel, monthParam } from "../money";

describe("baht", () => {
  it("groups exact decimal strings without float conversion", () => {
    expect(baht("0.00")).toBe("฿0.00");
    expect(baht("1234567.05")).toBe("฿1,234,567.05");
    expect(baht("90071992547409931.99")).toBe("฿90,071,992,547,409,931.99");
    expect(baht("-90.12")).toBe("−฿90.12");
  });

  it("rejects anything that is not a two-decimal string", () => {
    for (const bad of ["12", "12.3", "1e3", "", "12.345", "abc"]) {
      expect(() => baht(bad)).toThrow("INVALID_AMOUNT");
    }
  });
});

describe("isNegative", () => {
  it("treats negative zero as non-negative", () => {
    expect(isNegative("-0.01")).toBe(true);
    expect(isNegative("-0.00")).toBe(false);
    expect(isNegative("5.00")).toBe(false);
  });
});

describe("dates", () => {
  it("formats Buddhist Era labels", () => {
    expect(monthLabel(10, 2569)).toBe("ต.ค. 2569");
    expect(calendarDate("2026-01-02")).toBe("2 ม.ค. 2569");
    expect(monthParam(2026, 3)).toBe("2026-03");
  });
});
