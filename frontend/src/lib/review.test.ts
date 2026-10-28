import { describe, expect, it } from "vitest"
import { reviewProfile } from "./review"

describe("reviewProfile", () => {
  it("keeps mixed-language values and dates verbatim", () => {
    const profile = reviewProfile({ contact: { full_name: "علی رضایی" }, skills: ["Python", "طراحی"], work_experience: [{ start_date: "مهر ۱۴۰۱" }] })
    expect(profile.contact.full_name).toBe("علی رضایی")
    expect(profile.skills).toEqual(["Python", "طراحی"])
    expect(profile.work_experience[0].start_date).toBe("مهر ۱۴۰۱")
  })
  it("handles missing and invalid partial model output without executing it", () => {
    const profile = reviewProfile({ contact: "invalid", skills: [4, "Python"], education: null })
    expect(profile.contact.full_name).toBeNull()
    expect(profile.skills).toEqual(["Python"])
    expect(profile.education).toEqual([])
    expect(reviewProfile(null).work_experience).toEqual([])
  })
})
