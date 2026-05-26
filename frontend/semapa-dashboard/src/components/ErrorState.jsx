function ErrorState({ message = "Ocurrió un error al cargar los datos." }) {
  return (
    <div className="lay-state-box lay-state-error">
      <strong>{message}</strong>
    </div>
  );
}

export default ErrorState;