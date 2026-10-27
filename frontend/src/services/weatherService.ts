/**
 * Open-Meteo Weather Service
 * Fetches real-time ambient wind speed, direction, temperature, and condition
 * without requiring any API keys.
 */

export interface LiveWeatherData {
  wind_speed_mps: number;
  wind_direction_deg: number;
  wind_gusts_mps: number;
  temperature_c: number;
  weather_condition: string;
  retrieved_at: string;
  source: string;
}

// Map WMO weather codes to readable descriptions
function decodeWmoCode(code: number): string {
  if (code === 0) return "CLEAR_SKY";
  if (code === 1 || code === 2) return "PARTLY_CLOUDY";
  if (code === 3) return "OVERCAST";
  if (code === 45 || code === 48) return "FOG";
  if (code >= 51 && code <= 55) return "LIGHT_DRIZZLE";
  if (code >= 61 && code <= 65) return "RAIN";
  if (code >= 71 && code <= 77) return "SNOW";
  if (code >= 80 && code <= 82) return "RAIN_SHOWERS";
  if (code >= 95 && code <= 99) return "THUNDERSTORM";
  return "MODERATE_CLOUDS";
}

export async function fetchOpenMeteoWeather(
  latitude: number,
  longitude: number
): Promise<LiveWeatherData> {
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude.toFixed(
    4
  )}&longitude=${longitude.toFixed(
    4
  )}&current=temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code&wind_speed_unit=ms`;

  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!response.ok) {
      throw new Error(`Open-Meteo HTTP ${response.status}`);
    }
    const data = await response.json();
    const current = data.current;

    return {
      wind_speed_mps: current.wind_speed_10m ?? 4.5,
      wind_direction_deg: current.wind_direction_10m ?? 240,
      wind_gusts_mps: current.wind_gusts_10m ?? current.wind_speed_10m + 2.0,
      temperature_c: current.temperature_2m ?? 18.0,
      weather_condition: decodeWmoCode(current.weather_code ?? 1),
      retrieved_at: new Date().toISOString(),
      source: "OPEN_METEO_API",
    };
  } catch (err) {
    console.warn("Open-Meteo live weather fetch fallback:", err);
    // Return safe fallback values if offline or rate limited
    return {
      wind_speed_mps: 4.8,
      wind_direction_deg: 240.0,
      wind_gusts_mps: 7.2,
      temperature_c: 19.0,
      weather_condition: "PARTLY_CLOUDY",
      retrieved_at: new Date().toISOString(),
      source: "OFFLINE_FALLBACK",
    };
  }
}
