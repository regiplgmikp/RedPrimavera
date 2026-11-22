import Carpi from './Carpi.jsx';

// Carpi confundida, mirando la hora: se muestra cuando la API no responde o falla.
export default function ErrorCarpi({ mensaje, onReintentar }) {
  return (
    <div className="msg" role="alert">
      <div className="error-carpi">
        <div className="error-carpi-figura">
          <Carpi pose="curiosa" tamano={110} />
          <svg className="error-reloj" viewBox="0 0 40 40" width="38" height="38" aria-hidden="true">
            <circle cx="20" cy="20" r="17" fill="var(--panel)" stroke="var(--accent)" strokeWidth="3" />
            <path d="M20 20 L26 23" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
            <g className="agujas">
              <path d="M20 20 V9" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
            </g>
          </svg>
        </div>
        <p>{mensaje}</p>
        {onReintentar && <button type="button" className="primario" onClick={onReintentar}>Reintentar</button>}
      </div>
    </div>
  );
}