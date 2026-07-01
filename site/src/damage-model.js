(function exposeDamageModel(root) {
  "use strict";

  const unsupportedTerms = [
    ["pellet", "Pellet and shotgun damage is not modeled."],
    ["shotgun", "Pellet and shotgun damage is not modeled."],
    ["splash", "Splash damage is not modeled."],
    ["explosion", "Explosion damage is not modeled."],
    ["burn", "Damage over time is not modeled."],
    ["over time", "Damage over time is not modeled."],
    ["charge", "Charge-scaled damage is not modeled."],
    ["deployable", "Deployable damage is not modeled."],
    ["turret", "Deployable damage is not modeled."],
  ];

  function finite(value) {
    if (value === null || value === undefined || value === "") return null;
    return Number.isFinite(Number(value)) ? Number(value) : null;
  }

  function textFor(ability) {
    return [
      ability?.name,
      ability?.type,
      ability?.slot,
      ...(ability?.shot_type || []),
      ability?.stats?.damage?.raw_display,
      ability?.stats?.damage?.raw,
      ability?.raw_display?.description,
      ability?.raw_display?.official_description,
      ability?.raw_display?.["official description"],
      ability?.raw_display?.ability_keywords,
      ability?.raw_display?.["ability keywords"],
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function classify(ability) {
    const text = textFor(ability);
    const explicit = unsupportedTerms.find(([term]) => text.includes(term));
    if (explicit) return { supported: false, reason: explicit[1] };
    if (ability?.stats?.damage?.components?.length) {
      return { supported: false, reason: "Multi-component damage is not safely reducible to one hit." };
    }
    const damage = ability?.stats?.damage;
    const maximum = finite(damage?.max_value) ?? finite(damage?.value);
    const minimum = finite(damage?.min_value) ?? maximum;
    if (maximum === null || minimum === null || maximum <= 0 || minimum <= 0) {
      return { supported: false, reason: "A positive simple damage value was not safely parsed." };
    }
    const falloff = ability?.stats?.damage_falloff_range;
    const start = finite(falloff?.min_value);
    const end = finite(falloff?.max_value);
    const hasFalloff = start !== null && end !== null && end > start && maximum !== minimum;
    const partialFalloff = start !== null && end !== null && end > start && maximum === minimum;
    if (maximum !== minimum && !hasFalloff) {
      return { supported: false, reason: "Damage has a range but no safe distance mapping." };
    }
    const fireRate = finite(ability?.stats?.fire_rate?.value);
    const headshot = finite(ability?.stats?.headshot_mod?.value);
    const headshotText = String(ability?.stats?.headshot?.value ?? ability?.stats?.headshot?.raw ?? "").toLowerCase();
    const canHeadshot = headshot !== null && headshot > 1 && !/no|false|cannot/.test(headshotText);
    const damageType = text.includes("armor piercing") ? "armor_piercing" : (text.includes("beam") ? "beam" : "normal");
    return {
      supported: true, maximum, minimum, hasFalloff, partialFalloff, start, end,
      fireRate: fireRate && fireRate > 0 ? fireRate : null,
      canHeadshot, headshotMultiplier: canHeadshot ? headshot : null, damageType,
    };
  }

  function evaluate({ ruleset, ability, distance = 0, headshot = false } = {}) {
    const model = classify(ability);
    if (!model.supported) return { ...model, ruleset };
    const meters = Math.max(0, finite(distance) ?? 0);
    if (model.partialFalloff && meters > model.start) {
      return { ...model, supported: false, ruleset, distance: meters, reason: "Reduced damage after falloff start was not safely parsed." };
    }
    let damage = model.maximum;
    if (model.hasFalloff && meters > model.start) {
      const progress = Math.min(1, (meters - model.start) / (model.end - model.start));
      damage = model.maximum + (model.minimum - model.maximum) * progress;
    }
    if (headshot && model.canHeadshot) damage *= model.headshotMultiplier;
    return {
      ...model, ruleset, distance: meters, headshot: Boolean(headshot && model.canHeadshot),
      damage, dps: model.fireRate ? damage * model.fireRate : null,
    };
  }

  function damageToArmor(damage, damageType = "normal") {
    const amount = finite(damage);
    if (amount === null || amount <= 0) return null;
    if (damageType === "beam") return amount * 0.7;
    if (damageType === "normal") return Math.max(amount - 7, amount * 0.5);
    return null;
  }

  function rawDamageToBreakArmor(armor, damageType = "normal") {
    const amount = finite(armor);
    if (amount === null || amount <= 0) return 0;
    if (damageType === "beam") return amount / 0.7;
    if (damageType === "normal") return amount <= 7 ? amount * 2 : amount + 7;
    return null;
  }

  function shotsToKill({ ruleset, ability, target, distance = 0, headshot = false } = {}) {
    const hit = evaluate({ ruleset, ability, distance, headshot });
    if (!hit.supported) return hit;
    let health = Math.max(0, finite(target?.health) ?? 0);
    let armor = Math.max(0, finite(target?.armor) ?? 0);
    let shield = Math.max(0, finite(target?.shield) ?? 0);
    if (health + armor + shield <= 0) return { supported: false, reason: "Target health is unavailable." };
    let shots = 0;
    while (health + armor + shield > 0 && shots < 10000) {
      let remaining = hit.damage;
      const shieldDamage = Math.min(shield, remaining);
      shield -= shieldDamage;
      remaining -= shieldDamage;
      if (remaining > 0 && armor > 0) {
        const mitigated = damageToArmor(remaining, hit.damageType);
        if (mitigated === null) return { supported: false, reason: "This damage type has no safe armor rule." };
        if (mitigated <= armor) {
          armor -= mitigated;
          remaining = 0;
        } else {
          const rawConsumed = rawDamageToBreakArmor(armor, hit.damageType);
          if (rawConsumed === null) return { supported: false, reason: "This damage type has no safe armor rule." };
          armor = 0;
          remaining = Math.max(0, remaining - rawConsumed);
        }
      }
      health = Math.max(0, health - remaining);
      shots += 1;
    }
    return { ...hit, shots, targetTotal: (finite(target?.health) ?? 0) + (finite(target?.armor) ?? 0) + (finite(target?.shield) ?? 0) };
  }

  root.OWDamageModel = { classify, evaluate, damageToArmor, rawDamageToBreakArmor, shotsToKill };
}(typeof window === "undefined" ? globalThis : window));
