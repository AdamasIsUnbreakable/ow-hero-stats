(() => {
  const originalAbilityNotes = window.abilityNotes;
  const originalRenderAbilityNotes = window.renderAbilityNotes;

  if (typeof originalAbilityNotes !== "function" || typeof originalRenderAbilityNotes !== "function") {
    return;
  }

  window.abilityNotes = function cleanedAbilityNotes(ability) {
    return uniqueCleanGameplayNotes(originalAbilityNotes(ability));
  };

  window.renderAbilityNotes = function renderCleanAbilityNotes(notes) {
    return originalRenderAbilityNotes(uniqueCleanGameplayNotes(notes));
  };

  function uniqueCleanGameplayNotes(notes) {
    const seen = new Set();
    const cleaned = [];
    for (const note of notes || []) {
      const text = cleanGameplayNote(note);
      if (!text || seen.has(text)) {
        continue;
      }
      seen.add(text);
      cleaned.push(text);
    }
    return cleaned;
  }

  function cleanGameplayNote(note) {
    return String(note || "")
      .replace(/\s+/g, " ")
      .replace(/\s+([,.;:!?])/g, "$1")
      .replace(/([([{])\s+/g, "$1")
      .replace(/\s+([)\]}])/g, "$1")
      .replace(/\s*([-/])\s*/g, "$1")
      .replace(/\s*(×)\s*/g, " $1 ")
      .replace(/\s*([+])\s*/g, " $1 ")
      .replace(/\s*%\b/g, "%")
      .replace(/\b([A-Z][a-z]+) ’s\b/g, "$1’s")
      .replace(/\b([A-Z][a-z]+) 's\b/g, "$1's")
      .replace(/^[-*•]\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
  }
})();
