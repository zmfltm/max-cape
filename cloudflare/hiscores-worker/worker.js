const PLAYER = "gxexe";
const HISCORES_URL =
  `https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player=${encodeURIComponent(PLAYER)}`;
const ALLOWED_ORIGINS = new Set([
  "https://zmfltm.github.io",
  "http://127.0.0.1:8412",
  "http://localhost:8412",
]);
const SKILLS = new Set([
  "Attack", "Defence", "Strength", "Hitpoints", "Ranged", "Prayer",
  "Magic", "Cooking", "Woodcutting", "Fletching", "Fishing", "Firemaking",
  "Crafting", "Smithing", "Mining", "Herblore", "Agility", "Thieving",
  "Slayer", "Farming", "Runecraft", "Hunter", "Construction", "Sailing",
]);

function isAllowedOrigin(origin) {
  if (ALLOWED_ORIGINS.has(origin)) return true;
  try {
    const url = new URL(origin);
    const privateHost = /^10\./.test(url.hostname) ||
      /^192\.168\./.test(url.hostname) ||
      /^172\.(1[6-9]|2\d|3[01])\./.test(url.hostname);
    return url.protocol === "http:" && url.port === "8412" && privateHost;
  } catch (error) {
    return false;
  }
}

function corsHeaders(request) {
  const origin = request.headers.get("Origin");
  const headers = {
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
  if (origin && isAllowedOrigin(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

function json(request, data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders(request),
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": status === 200 ? "public, max-age=60" : "no-store",
    },
  });
}

function combatLevel(levels) {
  const level = (name) => levels[name] || 1;
  const base = 0.25 *
    (level("Defence") + level("Hitpoints") + Math.floor(level("Prayer") / 2));
  const melee = (13 / 40) * (level("Attack") + level("Strength"));
  const ranged = (13 / 40) * Math.floor(level("Ranged") * 3 / 2);
  const magic = (13 / 40) * Math.floor(level("Magic") * 3 / 2);
  return Math.floor(base + Math.max(melee, ranged, magic));
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }
    if (request.method !== "GET" || url.pathname !== "/") {
      return json(request, { error: "Not found" }, 404);
    }

    try {
      const response = await fetch(HISCORES_URL, {
        headers: { "User-Agent": "mudkip-osrs-plan/1.0" },
        cf: { cacheEverything: true, cacheTtl: 60 },
      });
      if (!response.ok) {
        return json(request, { error: `OSRS Hiscores returned ${response.status}` }, 502);
      }

      const source = await response.json();
      if (!source || !Array.isArray(source.skills)) {
        return json(request, { error: "OSRS Hiscores returned invalid data" }, 502);
      }

      const skills = {};
      let overall = null;
      for (const entry of source.skills) {
        if (!entry || !Number.isInteger(entry.level)) continue;
        const record = { level: entry.level, xp: entry.xp, rank: entry.rank };
        if (entry.name === "Overall") overall = record;
        else if (SKILLS.has(entry.name)) skills[entry.name] = record;
      }
      if (!overall || Object.keys(skills).length < 23) {
        return json(request, { error: "OSRS Hiscores response was incomplete" }, 502);
      }

      const levels = Object.fromEntries(
        Object.entries(skills).map(([name, record]) => [name, record.level]),
      );
      return json(request, {
        name: PLAYER,
        overall,
        combat: combatLevel(levels),
        skills,
      });
    } catch (error) {
      return json(request, { error: "Could not reach OSRS Hiscores" }, 502);
    }
  },
};
