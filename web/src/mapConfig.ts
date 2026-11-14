/** Map-only constants and types kept outside Map.tsx so the landing route does not pull MapLibre into its entry chunk. */
export const FIRE_LAYERS = [
  { id: "VIIRS_NOAA20_Thermal_Anomalies_375m_All", label: "VIIRS NOAA-20", color: "#8BD17C", from: "2020-01-01" },
  { id: "VIIRS_NOAA21_Thermal_Anomalies_375m_All", label: "VIIRS NOAA-21", color: "#D98BE8", from: "2024-01-17" },
  { id: "VIIRS_SNPP_Thermal_Anomalies_375m_All", label: "VIIRS Suomi-NPP", color: "#5CC8E6", from: "2012-01-20" },
  { id: "MODIS_Combined_Thermal_Anomalies_All", label: "MODIS Terra+Aqua", color: "#F2A541", from: "2002-07-04" },
] as const;

export type Basemap = "dark" | "night" | "satellite" | "relief";
export type Projection = "globe" | "mercator";
export type Layers = { fires: Record<string, boolean>; grid: boolean; statics: boolean; outlook: boolean };
export type Focus = { bbox?: number[]; center?: [number, number]; zoom?: number; n: number };

export const OUTLOOK_COLOR = { watch: "#FF3B2F", above: "#FF9A3C", season: "#F6C64F" } as const;
export const OUTLOOK_LABEL = {
  watch: "Watch: fire season ahead and running above normal",
  above: "Above normal for the time of year",
  season: "Fire season: the next 30 days are usually active",
} as const;
