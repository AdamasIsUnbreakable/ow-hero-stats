(function exposeDamageModel(root) {
  "use strict";

  function finite(value) {
    if (value === null || value === undefined || value === "") return null;
    return Number.isFinite(Number(value)) ? Number(value) : null;
  }

  function textFor(ability) {
    return [
      ability?.name, ability?.type, ability?.slot, ...(ability?.shot_type || []),
      ability?.stats?.damage?.raw_display, ability?.stats?.damage?.raw,
      ability?.raw_display?.description, ability?.raw_display?.official_description,
      ability?.raw_display?.["official description"], ability?.raw_display?.ability_keywords,
      ability?.raw_display?.["ability keywords"],
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function componentLabel(component) {
    return String(component?.label || "").toLowerCase();
  }

  function componentValues(component) {
    const maximum = finite(component?.max_value) ?? finite(component?.value);
    const minimum = finite(component?.min_value) ?? maximum;
    return { maximum, minimum };
  }

  function isRepeatable(ability) {
    const type = String(ability?.type || "").toLowerCase();
    const slot = String(ability?.slot || "").toLowerCase();
    return type.includes("weapon") || slot.includes("primary fire") || slot.includes("secondary fire");
  }

  function abilityCategory(ability) {
    return isRepeatable(ability) ? "repeatable" : "limited";
  }

  function damageTypeFor(text) {
    if (text.includes("armor piercing")) return "armor_piercing";
    if (text.includes("beam")) return "beam";
    return "normal";
  }

  function parsedRange(stat) {
    let maximum = finite(stat?.max_value) ?? finite(stat?.value);
    let minimum = finite(stat?.min_value) ?? maximum;
    const raw = String(stat?.raw_display ?? stat?.raw ?? "").trim();
    if (maximum === null && /[-–—]|â€“/.test(raw)) {
      const numbers = raw.match(/\d+(?:\.\d+)?/g)?.map(Number) || [];
      if (numbers.length === 2) {
        maximum = Math.max(...numbers);
        minimum = Math.min(...numbers);
      }
    }
    return { maximum, minimum };
  }

  function falloffModel(ability, maximum, minimum) {
    const falloff = ability?.stats?.damage_falloff_range;
    const start = finite(falloff?.min_value);
    const end = finite(falloff?.max_value);
    const hasFalloff = start !== null && end !== null && end > start && maximum !== minimum;
    const partialFalloff = start !== null && end !== null && end > start && maximum === minimum;
    return { start, end, hasFalloff, partialFalloff };
  }

  function explosionModel(ability, components, text) {
    const explosion = components.find((component) => {
      const label = componentLabel(component);
      return /(explosion|splash|aoe)/.test(label) && !/self/.test(label);
    });
    const radius = ability?.stats?.radius;
    const radialAreaDamage = /area of effect/.test(text)
      && finite(radius?.min_value) !== null
      && finite(radius?.max_value) !== null
      && finite(ability?.stats?.damage_falloff_range?.min_value) === null;
    const simpleExplosion = !components.length && (/(explod|splash)/.test(text) || radialAreaDamage);
    if (!explosion && !simpleExplosion) return null;
    const values = explosion ? componentValues(explosion) : parsedRange(ability?.stats?.damage);
    const start = finite(radius?.min_value);
    const end = finite(radius?.max_value);
    if (values.maximum === null || values.minimum === null || start === null || end === null || end <= start) {
      return { supported: false, reason: "Explosion damage needs safe minimum, maximum, and radius falloff data." };
    }
    const impact = components.find((component) => /direct hit|impact/.test(componentLabel(component)) && !/self/.test(componentLabel(component)));
    const impactDamage = impact ? componentValues(impact).maximum : 0;
    return { supported: true, maximum: values.maximum, minimum: values.minimum, explosionStart: start, explosionEnd: end, impactDamage: impactDamage || 0, defaultDirectHit: true };
  }

  function dotModel(ability, components, text) {
    let dot = components.find((component) => {
      const label = componentLabel(component);
      return /(burn|over time|dot)/.test(label) && !/self/.test(label);
    });
    const totalComponent = components.find((component) => /^total$|total damage/.test(componentLabel(component)));
    const perSecondComponent = components.find((component) => /per second/.test(componentLabel(component)));
    if (!dot && totalComponent && perSecondComponent) dot = totalComponent;
    const raw = String(dot?.raw_display ?? dot?.raw ?? ability?.stats?.damage?.raw_display ?? ability?.stats?.damage?.raw ?? "");
    const simpleDot = !components.length
      && !/(deployable|turret|trap)/.test(text)
      && /(over\s+[\d.]+\s*seconds?|damage over time|burn|per second)/i.test(raw + " " + text);
    if (!dot && !simpleDot) return null;
    const total = dot ? componentValues(dot).maximum : parsedRange(ability?.stats?.damage).maximum;
    const duration = finite(ability?.stats?.duration?.value);
    const hasSafeDuration = /over\s+[\d.]+\s*seconds?/i.test(raw) || (duration !== null && duration > 0);
    if (total === null || total <= 0 || !hasSafeDuration) {
      return { supported: false, reason: "Damage over time needs a safely parsed total and duration." };
    }
    const tickMatch = raw.match(/deals\s+([\d.]+)\s+damage\s+every/i);
    const tickDamage = tickMatch ? finite(tickMatch[1]) : null;
    const tickCount = tickDamage ? Math.max(1, Math.round(total / tickDamage)) : null;
    return { supported: true, total, tickDamage, tickCount, dotMode: tickDamage ? "ticks" : "total" };
  }

  function shotgunModel(ability, components, text) {
    const fullShot = components.find((component) => /per (volley|blast)/.test(componentLabel(component)))
      || components.find((component) => /per shot/.test(componentLabel(component)) && !/per pellet/.test(componentLabel(component)));
    let pellet = components.find((component) => /per pellet/.test(componentLabel(component)));
    const volley = components.find((component) => /per (volley|blast)/.test(componentLabel(component)));
    if (!pellet && volley) pellet = components.find((component) => /per shot/.test(componentLabel(component)));
    if (!pellet && !/(pellet|shotgun)/.test(text)) return null;
    if (!fullShot) return { supported: false, reason: "Shotgun damage needs a safely parsed full-shot or full-volley damage value." };
    const shotValues = componentValues(fullShot);
    if (!shotValues.maximum) return { supported: false, reason: "Shotgun full-shot damage was not safely parsed." };
    if (!pellet) return { supported: true, pelletCount: null, fullMaximum: shotValues.maximum, fullMinimum: shotValues.minimum, maximum: shotValues.maximum, minimum: shotValues.minimum, hasFalloff: false, partialFalloff: false, allPelletsAssumed: true };
    const pelletValues = componentValues(pellet);
    if (!pelletValues.maximum || !shotValues.maximum) {
      return { supported: false, reason: "Shotgun pellet damage was not safely parsed." };
    }
    const pelletCount = Math.round(shotValues.maximum / pelletValues.maximum);
    if (pelletCount <= 0 || Math.abs(pelletCount * pelletValues.maximum - shotValues.maximum) > 0.05) {
      return { supported: false, reason: "Shotgun pellet count could not be derived safely." };
    }
    const falloff = falloffModel(ability, shotValues.maximum, shotValues.minimum);
    if (shotValues.maximum !== shotValues.minimum && !falloff.hasFalloff) {
      return { supported: false, reason: "Full-shot damage has a range but no safe distance mapping." };
    }
    return { supported: true, pelletCount, pelletMaximum: pelletValues.maximum, pelletMinimum: pelletValues.minimum, fullMaximum: shotValues.maximum, fullMinimum: shotValues.minimum, maximum: shotValues.maximum, minimum: shotValues.minimum, allPelletsAssumed: true, ...falloff };
  }

  function zaryaModel(ability, components) {
    const heroSlug = String(ability?.hero_slug || "").toLowerCase();
    const isZarya = heroSlug === "zarya" || /particle cannon/i.test(String(ability?.name || ""));
    if (!isZarya) return null;
    const enemyZero = components.find((component) => /enemy, 0% energy/.test(componentLabel(component)))
      || components.find((component) => /at 0%/.test(componentLabel(component)));
    const enemyHundred = components.find((component) => /enemy, 100% energy/.test(componentLabel(component)))
      || components.find((component) => /100% energy/.test(componentLabel(component)));
    if (!enemyZero || !enemyHundred) return { supported: false, reason: "Zarya damage needs explicit 0% and 100% Energy values." };
    const zero = componentValues(enemyZero);
    const hundred = componentValues(enemyHundred);
    const radius = ability?.stats?.radius;
    const explosionStart = finite(radius?.min_value);
    const explosionEnd = finite(radius?.max_value);
    const isExplosion = /alt fire|secondary/i.test(`${ability?.name} ${ability?.slot}`);
    if (isExplosion && (explosionStart === null || explosionEnd === null || explosionEnd <= explosionStart)) {
      return { supported: false, reason: "Zarya alternate fire needs safe explosion radius data." };
    }
    return {
      supported: true, zeroMaximum: zero.maximum, zeroMinimum: zero.minimum,
      hundredMaximum: hundred.maximum, hundredMinimum: hundred.minimum,
      isExplosion, explosionStart, explosionEnd, defaultDirectHit: isExplosion,
    };
  }

  function useCount(ability) {
    const explicit = finite(ability?.stats?.charges?.value);
    return explicit && explicit > 1 ? Math.min(Math.floor(explicit), 2) : 1;
  }

  function complexDamageReason(ability) {
    if (ability?.name === "Molten Core") return "Needs deployable uptime or a selected pool duration; impact, pool DPS, and armor bonus cannot be combined safely.";
    if (ability?.name === "Palatine Fang") return "Multiple swing and overhead-strike stages need an explicit combo-stage selection.";
    if (ability?.name === "Sundering Blade") return "Multiple charge stages and direct/indirect damage choices need an explicit stage selection.";
    return "Multi-component damage is not safely reducible to one modeled event.";
  }

  function vendettaStageModel(ability, components) {
    if (!['Palatine Fang', 'Sundering Blade'].includes(ability?.name)) return null;
    const stages = components.map((component, index) => ({
      label: `${ability.name === 'Sundering Blade' ? 'direct hit, ' : ''}${String(component?.label || `stage ${index + 1}`).replaceAll('[[', '').replaceAll(']]', '')}`,
      damage: componentValues(component).maximum,
    })).filter((stage) => stage.damage !== null && stage.damage > 0);
    if (!stages.length) return { supported: false, reason: "Needs combo-stage selection, but no positive stage damage was parsed." };
    return { supported: true, kind: "staged", stages, controls: ["stage"], unit: "shots" };
  }

  function classify(ability) {
    if (!ability) return { supported: false, reason: "Choose a weapon or ability." };
    const text = textFor(ability);
    const category = abilityCategory(ability);
    const components = ability?.stats?.damage?.components || [];
    const damageType = damageTypeFor(text);
    const base = { category, useCount: category === "limited" ? useCount(ability) : null, damageType };

    const zarya = zaryaModel(ability, components);
    if (zarya) return { ...base, ...zarya, kind: zarya.isExplosion ? "explosion" : "beam", controls: ["energy", ...(zarya.isExplosion ? ["explosionDistance"] : [])], unit: zarya.isExplosion ? "shots" : "seconds" };

    const shotgun = shotgunModel(ability, components, text);
    if (shotgun) return { ...base, ...shotgun, kind: "shotgun", controls: [...(shotgun.hasFalloff || shotgun.partialFalloff ? ["distance"] : [])], unit: "shots" };

    const vendettaStages = vendettaStageModel(ability, components);
    if (vendettaStages) return { ...base, ...vendettaStages };

    const explosion = explosionModel(ability, components, text);
    const dot = dotModel(ability, components, text);
    if (explosion || dot) {
      if (explosion && !explosion.supported) return { ...base, ...explosion, kind: "explosion", controls: [] };
      if (dot && !dot.supported) return { ...base, ...dot, kind: "dot", controls: [] };
      return {
        ...base, supported: true, kind: explosion && dot ? "explosion_dot" : (explosion ? "explosion" : "dot"),
        controls: explosion ? ["explosionDistance"] : [], ...explosion, dot,
        safePartOnly: components.some((component) => !/(direct hit|impact|explosion|splash|aoe|burn|over time|dot|self)/.test(componentLabel(component))),
        unit: category === "repeatable" ? "shots" : "uses",
      };
    }

    if (/deployable|turret|trap/.test(text)) {
      let values = parsedRange(ability?.stats?.damage);
      let sourceLabel = "";
      if ((!values.maximum || values.maximum !== values.minimum) && components.length) {
        const safeComponent = components.find((component) => /arm cannon|turret|per hit|per shot/.test(componentLabel(component)) && componentValues(component).maximum > 0);
        if (safeComponent) {
          values = componentValues(safeComponent);
          sourceLabel = componentLabel(safeComponent);
        }
      }
      if (!values.maximum || values.maximum !== values.minimum) return { ...base, supported: false, kind: "deployable", reason: "Deployable damage needs a safe per-hit, total, or damage-per-second value with duration." };
      const perSecond = /per second/.test(text) || /per second/.test(sourceLabel);
      return { ...base, supported: true, kind: "deployable", maximum: values.maximum, minimum: values.minimum, controls: [], unit: perSecond ? "seconds" : "hits", safePartOnly: true, modeledPart: sourceLabel || (perSecond ? "one second of damage" : "one hit") };
    }

    if (components.length) return { ...base, supported: false, kind: "complex", reason: complexDamageReason(ability) };
    const values = parsedRange(ability?.stats?.damage);
    if (values.maximum === null || values.minimum === null || values.maximum <= 0 || values.minimum <= 0) {
      return { ...base, supported: false, kind: "unknown", reason: "A positive damage value was not safely parsed." };
    }
    const falloff = falloffModel(ability, values.maximum, values.minimum);
    if (values.maximum !== values.minimum && !falloff.hasFalloff) {
      return { ...base, supported: false, kind: "direct", reason: "Damage has a range but no safe distance mapping." };
    }
    const fireRate = finite(ability?.stats?.fire_rate?.value);
    const headshot = finite(ability?.stats?.headshot_mod?.value);
    const headshotText = String(ability?.stats?.headshot?.value ?? ability?.stats?.headshot?.raw ?? "").toLowerCase();
    const canHeadshot = headshot !== null && headshot > 1 && !/no|false|cannot/.test(headshotText);
    return {
      ...base, supported: true, kind: /melee/.test(text) ? "melee" : "direct",
      maximum: values.maximum, minimum: values.minimum, ...falloff,
      fireRate: fireRate && fireRate > 0 ? fireRate : null,
      canHeadshot, headshotMultiplier: canHeadshot ? headshot : null,
      controls: [...(falloff.hasFalloff || falloff.partialFalloff ? ["distance"] : []), ...(canHeadshot ? ["headshot"] : [])],
      unit: /per second/.test(text) ? "seconds" : "shots",
    };
  }

  function interpolate(maximum, minimum, distance, start, end) {
    if (distance <= start) return maximum;
    const progress = Math.min(1, (distance - start) / (end - start));
    return maximum + (minimum - maximum) * progress;
  }

  function evaluate({ ruleset, ability, distance = 0, explosionDistance, pelletsHit, energy = 0, stage = 0, headshot = false } = {}) {
    const model = classify(ability);
    if (!model.supported) return { ...model, ruleset };
    const meters = Math.max(0, finite(distance) ?? 0);
    const explicitBlastDistance = finite(explosionDistance);
    const blastMeters = Math.max(0, explicitBlastDistance ?? 0);
    const charge = Math.min(100, Math.max(0, finite(energy) ?? 0));
    const parts = [];

    if (model.kind === "staged") {
      const selectedStage = Math.min(model.stages.length - 1, Math.max(0, Math.floor(finite(stage) ?? 0)));
      const selected = model.stages[selectedStage];
      parts.push({ label: selected.label, damage: selected.damage, damageType: model.damageType });
    } else if (model.kind === "shotgun") {
      if (model.partialFalloff && meters > model.start) return { ...model, supported: false, reason: "Reduced full-shot damage after falloff start was not safely parsed." };
      const fullDamage = model.hasFalloff ? interpolate(model.fullMaximum, model.fullMinimum, meters, model.start, model.end) : model.fullMaximum;
      const landed = model.pelletCount && finite(pelletsHit) !== null ? Math.min(model.pelletCount, Math.max(1, Math.round(finite(pelletsHit)))) : model.pelletCount;
      const damage = landed && landed !== model.pelletCount ? fullDamage * landed / model.pelletCount : fullDamage;
      parts.push({ label: landed && landed !== model.pelletCount ? `${landed} pellets` : "full shotgun shot", damage, damageType: model.damageType });
    } else if (model.controls.includes("energy")) {
      let maximum = model.zeroMaximum + (model.hundredMaximum - model.zeroMaximum) * charge / 100;
      let minimum = model.zeroMinimum + (model.hundredMinimum - model.zeroMinimum) * charge / 100;
      if (model.isExplosion && explicitBlastDistance !== null) maximum = interpolate(maximum, minimum, blastMeters, model.explosionStart, model.explosionEnd);
      parts.push({ label: `${charge}% Energy`, damage: maximum, damageType: model.damageType });
    } else if (model.kind === "explosion" || model.kind === "explosion_dot") {
      const splashDamage = explicitBlastDistance === null ? model.maximum : interpolate(model.maximum, model.minimum, blastMeters, model.explosionStart, model.explosionEnd);
      const impactDamage = explicitBlastDistance === null ? model.impactDamage : 0;
      parts.push({ label: explicitBlastDistance === null ? "direct hit / max explosion" : "splash", damage: splashDamage + impactDamage, damageType: model.damageType });
    } else if (model.kind !== "dot") {
      if (model.partialFalloff && meters > model.start) return { ...model, supported: false, reason: "Reduced damage after falloff start was not safely parsed." };
      let damage = model.hasFalloff ? interpolate(model.maximum, model.minimum, meters, model.start, model.end) : model.maximum;
      if (headshot && model.canHeadshot) damage *= model.headshotMultiplier;
      parts.push({ label: model.safePartOnly ? "safe modeled part" : "hit", damage, damageType: model.damageType });
    }

    if (model.dot) {
      if (model.dot.tickDamage && model.dot.tickCount) {
        for (let index = 0; index < model.dot.tickCount; index += 1) parts.push({ label: "DoT tick", damage: model.dot.tickDamage, damageType: model.damageType });
      } else {
        parts.push({ label: "total DoT", damage: model.dot.total, damageType: model.damageType, totalOnly: true });
      }
    } else if (model.kind === "dot") {
      const dotData = model.dot || model;
      if (dotData.tickDamage && dotData.tickCount) {
        for (let index = 0; index < dotData.tickCount; index += 1) parts.push({ label: "DoT tick", damage: dotData.tickDamage, damageType: model.damageType });
      } else parts.push({ label: "total DoT", damage: dotData.total, damageType: model.damageType, totalOnly: true });
    }

    const damage = parts.reduce((sum, part) => sum + part.damage, 0);
    return { ...model, ruleset, distance: meters, explosionDistance: blastMeters, energy: charge, headshot: Boolean(headshot && model.canHeadshot), damage, damageParts: parts, dps: model.fireRate ? damage * model.fireRate : null };
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

  function targetState(target) {
    return { health: Math.max(0, finite(target?.health) ?? 0), armor: Math.max(0, finite(target?.armor) ?? 0), shield: Math.max(0, finite(target?.shield) ?? 0) };
  }

  function stateTotal(state) {
    return state.health + state.armor + state.shield;
  }

  function applyDamagePart(state, part) {
    let remaining = part.damage;
    const shieldDamage = Math.min(state.shield, remaining);
    state.shield -= shieldDamage;
    remaining -= shieldDamage;
    if (remaining > 0 && state.armor > 0) {
      if (part.totalOnly) return { supported: false, reason: "Total-only damage over time cannot be applied safely to armor without tick data." };
      const mitigated = damageToArmor(remaining, part.damageType);
      if (mitigated === null) return { supported: false, reason: "This damage type has no safe armor rule." };
      if (mitigated <= state.armor) {
        state.armor -= mitigated;
        remaining = 0;
      } else {
        const consumed = rawDamageToBreakArmor(state.armor, part.damageType);
        if (consumed === null) return { supported: false, reason: "This damage type has no safe armor rule." };
        state.armor = 0;
        remaining = Math.max(0, remaining - consumed);
      }
    }
    state.health = Math.max(0, state.health - remaining);
    return { supported: true };
  }

  function applyEvaluation(state, evaluation) {
    for (const part of evaluation.damageParts || []) {
      const applied = applyDamagePart(state, part);
      if (!applied.supported) return applied;
      if (stateTotal(state) <= 0) break;
    }
    return { supported: true };
  }

  function shotsToKill(options = {}) {
    const hit = evaluate(options);
    if (!hit.supported) return hit;
    const state = targetState(options.target);
    const targetTotal = stateTotal(state);
    if (targetTotal <= 0) return { supported: false, reason: "Target health is unavailable." };
    let shots = 0;
    while (stateTotal(state) > 0 && shots < 10000) {
      const applied = applyEvaluation(state, hit);
      if (!applied.supported) return applied;
      shots += 1;
    }
    return { ...hit, shots, targetTotal, remaining: state };
  }

  function calculateCombo({ ruleset, weapon, weaponOptions = {}, abilities = [], target } = {}) {
    const state = targetState(target);
    const targetTotal = stateTotal(state);
    if (targetTotal <= 0) return { supported: false, reason: "Target health is unavailable." };
    let comboDamage = 0;
    const included = [];
    for (const event of abilities) {
      const evaluation = evaluate({ ruleset, ability: event.ability, ...(event.options || {}) });
      if (!evaluation.supported) return evaluation;
      comboDamage += evaluation.damage;
      const applied = applyEvaluation(state, evaluation);
      if (!applied.supported) return applied;
      included.push(event.label || event.ability?.name || "Ability");
      if (stateTotal(state) <= 0) break;
    }
    const remainingAfterCombo = stateTotal(state);
    if (remainingAfterCombo <= 0) return { supported: true, comboDamage, remainingAfterCombo: 0, weaponShots: 0, included, defeatedByCombo: true, targetTotal };
    if (!weapon) return { supported: true, comboDamage, remainingAfterCombo, weaponShots: null, included, defeatedByCombo: false, targetTotal };
    const weaponHit = evaluate({ ruleset, ability: weapon, ...weaponOptions });
    if (!weaponHit.supported) return weaponHit;
    let weaponShots = 0;
    while (stateTotal(state) > 0 && weaponShots < 10000) {
      const applied = applyEvaluation(state, weaponHit);
      if (!applied.supported) return applied;
      weaponShots += 1;
    }
    return { supported: true, comboDamage, remainingAfterCombo, weaponShots, included, defeatedByCombo: false, targetTotal, weaponHit };
  }

  root.OWDamageModel = { classify, evaluate, damageToArmor, rawDamageToBreakArmor, shotsToKill, calculateCombo };
}(typeof window === "undefined" ? globalThis : window));
