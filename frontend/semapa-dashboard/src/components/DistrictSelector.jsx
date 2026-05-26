function DistrictSelector({ distritos, value, onChange }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {(distritos || []).map((d) => (
        <option key={d.distrito} value={d.distrito}>
          Distrito {d.distrito}
        </option>
      ))}
    </select>
  );
}

export default DistrictSelector;