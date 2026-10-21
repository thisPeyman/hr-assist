declare module "jalaali-js" {
  export interface JalaaliDate {
    jy: number
    jm: number
    jd: number
  }
  export function toJalaali(gy: number, gm: number, gd: number): JalaaliDate
  export function toGregorian(jy: number, jm: number, jd: number): {
    gy: number
    gm: number
    gd: number
  }
  export function isValidJalaaliDate(jy: number, jm: number, jd: number): boolean
  export function isLeapJalaaliYear(jy: number): boolean
  const jalaali: {
    toJalaali: typeof toJalaali
    toGregorian: typeof toGregorian
    isValidJalaaliDate: typeof isValidJalaaliDate
    isLeapJalaaliYear: typeof isLeapJalaaliYear
  }
  export default jalaali
}
