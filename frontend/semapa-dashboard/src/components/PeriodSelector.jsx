function PeriodSelector({ value, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="2026-04">2026-04</option>
      <option value="2026-03">2026-03</option>
      <option value="2026-02">2026-02</option>
    </select>
  );
}

export default PeriodSelector;