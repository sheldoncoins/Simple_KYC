/** The seven supported markets (mirrors app/config.py COUNTRY_REGISTRY). */
export const COUNTRIES = [
  { iso: "IN", name: "India" },
  { iso: "NG", name: "Nigeria" },
  { iso: "BR", name: "Brazil" },
  { iso: "MX", name: "Mexico" },
  { iso: "CO", name: "Colombia" },
  { iso: "AR", name: "Argentina" },
  { iso: "VE", name: "Venezuela" },
] as const;

export type CountryIso = (typeof COUNTRIES)[number]["iso"];
