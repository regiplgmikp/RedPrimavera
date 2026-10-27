import { useState } from "react";
import "./CarpiPersonaje.css";

/* ---------- Colores y estilos compartidos ---------- */
const INK = "#2B2A35";
const WING = "#3A3946";
const WING_LINE = "#54536A";
const CREAM = "#FFF4E6";
const RED = "#E8484F";
const RED_DARK = "#D93A44";
const BEAK = {
  fill: "#F4B72E",
  stroke: "#C98A1E",
  strokeWidth: 2.5,
  strokeLinejoin: "round",
};

/* ---------- Vistas y expresiones ---------- */
const VIEWS = {
  frente: {
    label: "De frente",
    expressions: [
      "Feliz",
      "Curiosa",
      "Dormida",
      "Sorprendida",
      "Señalando",
      "Presentando",
      "Hablando",
      "Cargando",
    ],
  },
  perfil: {
    label: "De perfil",
    expressions: ["Sonriendo", "Hablando", "Sorprendida"],
  },
};

const ICONS = {
  Feliz: "☺",
  Sonriendo: "☺",
  Curiosa: "✦",
  Dormida: "☾",
  Sorprendida: "!",
  Señalando: "→",
  Presentando: "▤",
  Hablando: "…",
  Cargando: "◌",
};

// "Señalando" -> "senalando" (para usarlo como clase CSS)
const slug = (text) =>
  text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

/* ---------- Piezas pequeñas reutilizables ---------- */

// Dos pestañas. dir = -1 apunta a la izquierda, dir = 1 a la derecha
function Lashes({ x, y, dir }) {
  return (
    <path
      d={`M${x} ${y} l${6 * dir} -4 M${x - 3 * dir} ${y - 3} l${4 * dir} -6`}
      fill="none"
      stroke={INK}
      strokeWidth="2.5"
      strokeLinecap="round"
    />
  );
}

// Par de ojos abiertos con brillito
function OpenEyes({ left, right, y, rx, ry, shine }) {
  return (
    <>
      <ellipse cx={left} cy={y} rx={rx} ry={ry} fill={INK} />
      <ellipse cx={right} cy={y} rx={rx} ry={ry} fill={INK} />
      <circle cx={left + 3} cy={y - 4} r={shine} fill="white" />
      <circle cx={right + 3} cy={y - 4} r={shine} fill="white" />
    </>
  );
}

/* =====================================================
   VISTA DE FRENTE
   ===================================================== */

const happyFrontEyes = (
  <>
    <OpenEyes left={97} right={143} y={120} rx={9} ry={11} shine={3.5} />
    <Lashes x={90} y={113} dir={-1} />
    <Lashes x={150} y={113} dir={1} />
  </>
);

const frontEyes = {
  Feliz: happyFrontEyes,
  Hablando: happyFrontEyes,
  Curiosa: (
    <>
      <OpenEyes left={97} right={143} y={119} rx={11} ry={14} shine={4.5} />
      <circle cx="94" cy="124" r="2" fill="white" />
      <circle cx="140" cy="124" r="2" fill="white" />
      <Lashes x={88} y={110} dir={-1} />
      <Lashes x={152} y={110} dir={1} />
    </>
  ),
  Dormida: (
    <>
      <path
        d="M87 120 Q97 129 107 120 M133 120 Q143 129 153 120"
        fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round"
      />
      <path
        d="M89 123 l-5 5 M93 125 l-2 6 M151 123 l5 5 M147 125 l2 6"
        fill="none" stroke={INK} strokeWidth="2.5" strokeLinecap="round"
      />
    </>
  ),
  Sorprendida: (
    <>
      <path
        d="M86 99 Q97 92 108 99 M132 99 Q143 92 154 99"
        fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round"
      />
      <circle cx="97" cy="119" r="12" fill="white" stroke={INK} strokeWidth="3" />
      <circle cx="143" cy="119" r="12" fill="white" stroke={INK} strokeWidth="3" />
      <circle cx="97" cy="119" r="5" fill={INK} />
      <circle cx="143" cy="119" r="5" fill={INK} />
      <Lashes x={87} y={111} dir={-1} />
      <Lashes x={153} y={111} dir={1} />
    </>
  ),
  Señalando: (
    <>
      <OpenEyes left={101} right={147} y={120} rx={9} ry={11} shine={3.5} />
      <Lashes x={94} y={113} dir={-1} />
      <Lashes x={154} y={113} dir={1} />
    </>
  ),
  Presentando: (
    <>
      <path
        d="M88 122 Q97 111 106 122 M134 122 Q143 111 152 122"
        fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round"
      />
      <Lashes x={89} y={119} dir={-1} />
      <Lashes x={151} y={119} dir={1} />
    </>
  ),
  Cargando: (
    <>
      <OpenEyes left={99} right={145} y={117} rx={9} ry={11} shine={3.5} />
      <Lashes x={92} y={110} dir={-1} />
      <Lashes x={152} y={110} dir={1} />
    </>
  ),
};

function FrontBeak({ expression }) {
  const upper = (
    <>
      <ellipse cx="120" cy="143" rx="6" ry="6" fill="#7A2F35" />
      <path d="M110 130 Q120 124 130 130 L120 139 Z" {...BEAK} />
    </>
  );
  const lower = <path d="M114 147 Q120 145 126 147 L120 155 Z" {...BEAK} />;

  if (expression === "Sorprendida") {
    return <>{upper}{lower}</>;
  }
  if (expression === "Hablando") {
    return <>{upper}<g className="carpi-jaw">{lower}</g></>;
  }
  return <path d="M110 132 Q120 126 130 132 L120 147 Z" {...BEAK} />;
}

function CarpiFront({ expression }) {
  const showSpark = !["Presentando", "Hablando", "Cargando"].includes(expression);

  return (
    <svg
      className="carpi-bird"
      viewBox="0 0 240 290"
      role="img"
      aria-label={`Carpi de frente, ${expression.toLowerCase()}`}
    >
      {/* Cola */}
      <path d="M104 244 Q96 280 116 252 Z" fill={WING} />
      <path d="M136 244 Q144 280 124 252 Z" fill={WING} />
      <path d="M111 246 Q120 292 129 246 Z" fill={INK} />

      {/* Patitas */}
      <g fill="none" stroke="#E9A13B" strokeWidth="5" strokeLinecap="round">
        <path d="M104 254 L100 268 M100 268 L92 272 M100 268 L107 273" />
        <path d="M136 254 L140 268 M140 268 L133 273 M140 268 L148 272" />
      </g>

      {/* Cuerpo y pancita con plumitas */}
      <ellipse cx="120" cy="205" rx="58" ry="55" fill={INK} />
      <ellipse cx="120" cy="216" rx="36" ry="38" fill={CREAM} />
      <path
        d="M100 200 q4 5 8 0 M112 200 q4 5 8 0 M124 200 q4 5 8 0 M136 200 q4 5 8 0
           M94 214 q4 5 8 0 M106 214 q4 5 8 0 M118 214 q4 5 8 0 M130 214 q4 5 8 0 M142 214 q4 5 8 0
           M98 228 q4 5 8 0 M110 228 q4 5 8 0 M122 228 q4 5 8 0 M134 228 q4 5 8 0
           M108 242 q4 5 8 0 M120 242 q4 5 8 0"
        fill="none" stroke="#E8D5BD" strokeWidth="2" strokeLinecap="round"
      />

      {/* Ala izquierda */}
      <g transform="rotate(18 66 208)">
        <ellipse cx="66" cy="208" rx="15" ry="30" fill={WING} />
        <path
          d="M53 222 L53 238 Q56 249 61 242 Q66 254 71 242 Q76 249 79 238 L79 222 Z"
          fill={WING}
        />
        <path
          d="M55 198 Q66 205 77 198 M54 212 Q66 219 78 212"
          fill="none" stroke={WING_LINE} strokeWidth="2" strokeLinecap="round"
        />
        <g fill={CREAM}>
          <circle cx="66" cy="190" r="3" />
          <circle cx="60" cy="226" r="2.5" />
          <circle cx="72" cy="226" r="2.5" />
        </g>
      </g>

      {/* Tarjetita (Presentando) */}
      {expression === "Presentando" && (
        <g>
          <rect x="192" y="164" width="46" height="36" rx="6" fill="white" stroke="#E8D5BD" strokeWidth="2" />
          <rect x="200" y="182" width="7" height="12" rx="1.5" fill="#F4B72E" />
          <rect x="211" y="175" width="7" height="19" rx="1.5" fill={RED} />
          <rect x="222" y="179" width="7" height="15" rx="1.5" fill={INK} />
        </g>
      )}

      {/* Ala derecha (se mueve al señalar y presentar) */}
      <g className="carpi-wing-r">
        <g transform="rotate(-18 174 208)">
          <ellipse cx="174" cy="208" rx="15" ry="30" fill={WING} />
          <path
            d="M187 222 L187 238 Q184 249 179 242 Q174 254 169 242 Q164 249 161 238 L161 222 Z"
            fill={WING}
          />
          <path
            d="M185 198 Q174 205 163 198 M186 212 Q174 219 162 212"
            fill="none" stroke={WING_LINE} strokeWidth="2" strokeLinecap="round"
          />
          <g fill={CREAM}>
            <circle cx="174" cy="190" r="3" />
            <circle cx="168" cy="226" r="2.5" />
            <circle cx="180" cy="226" r="2.5" />
          </g>
        </g>
      </g>

      {/* Mechones redondos de los lados */}
      <g fill={INK}>
        <ellipse cx="52" cy="121" rx="11" ry="7" transform="rotate(-15 52 121)" />
        <ellipse cx="55" cy="140" rx="11" ry="7" transform="rotate(20 55 140)" />
        <ellipse cx="188" cy="121" rx="11" ry="7" transform="rotate(15 188 121)" />
        <ellipse cx="185" cy="140" rx="11" ry="7" transform="rotate(-20 185 140)" />
      </g>

      {/* Cabeza */}
      <circle cx="120" cy="112" r="68" fill={INK} />

      {/* Copete */}
      <path d="M96 52 Q88 32 100 22 Q101 38 112 48 Z" fill={RED_DARK} />
      <path d="M106 48 Q108 20 126 14 Q120 32 132 46 Z" fill={RED} />
      <path d="M124 46 Q134 26 150 26 Q138 38 142 50 Z" fill={RED_DARK} />

      {/* Gorrito rojo (baja hasta la carita) */}
      <path d="M52 110 A68 68 0 0 1 188 110 Z" fill={RED} />

      {/* Carita y plumón del cuello */}
      <ellipse cx="120" cy="126" rx="52" ry="42" fill={CREAM} />
      <path
        d="M92 166 Q96 184 104 178 Q108 192 116 182 Q120 196 124 182 Q132 192 136 178 Q144 184 148 166 Z"
        fill={CREAM}
      />

      {/* Plumitas y brillo del gorro */}
      <path
        d="M76 74 q5 4 10 0 M98 62 q5 4 10 0 M120 60 q5 4 10 0 M142 64 q5 4 10 0 M158 76 q5 4 10 0"
        fill="none" stroke="#C9353D" strokeWidth="2" strokeLinecap="round"
      />
      <path d="M74 64 Q88 54 104 52" fill="none" stroke="#FF8A80" strokeWidth="4" strokeLinecap="round" />

      {/* Cachetes */}
      <ellipse cx="82" cy="140" rx="10" ry="6" fill="#FFB3AB" />
      <ellipse cx="158" cy="140" rx="10" ry="6" fill="#FFB3AB" />

      {/* Ojos y pico */}
      {frontEyes[expression]}
      <FrontBeak expression={expression} />

      {/* Extras según la expresión */}
      {showSpark && (
        <path
          d="M196 56 L199 64 L207 67 L199 70 L196 78 L193 70 L185 67 L193 64 Z"
          fill="#F4B72E"
        />
      )}

      {expression === "Sorprendida" && (
        <text x="182" y="104" fontSize="30" fontWeight="500" fill={RED}>!</text>
      )}

      {expression === "Hablando" && <SpeechBubble x={168} y={18} />}

      {expression === "Cargando" && (
        <g>
          <circle cx="196" cy="62" r="13" fill="none" stroke="#F3D9CF" strokeWidth="5" />
          <path
            className="carpi-spinner"
            d="M196 49 A13 13 0 0 1 209 62"
            fill="none" stroke={RED} strokeWidth="5" strokeLinecap="round"
          />
        </g>
      )}
    </svg>
  );
}

// Globito de diálogo con tres puntitos
function SpeechBubble({ x, y }) {
  return (
    <g>
      <path
        d={`M${x} ${y} h36 a14 14 0 0 1 0 28 h-26 l-8 8 l1 -8 h-3 a14 14 0 0 1 0 -28 Z`}
        fill="white" stroke="#E8D5BD" strokeWidth="2"
      />
      <g fill={RED}>
        <circle className="carpi-dot" cx={x + 8} cy={y + 14} r="3.5" />
        <circle className="carpi-dot" cx={x + 20} cy={y + 14} r="3.5" />
        <circle className="carpi-dot" cx={x + 32} cy={y + 14} r="3.5" />
      </g>
    </g>
  );
}

/* =====================================================
   VISTA DE PERFIL (mirando a la derecha)
   ===================================================== */

const profileEyes = {
  Sonriendo: (
    <>
      <path d="M148 121 Q157 110 166 121" fill="none" stroke={INK} strokeWidth="4" strokeLinecap="round" />
      <Lashes x={149} y={118} dir={-1} />
    </>
  ),
  Hablando: (
    <>
      <ellipse cx="156" cy="118" rx="8" ry="10" fill={INK} />
      <circle cx="159" cy="114" r="3" fill="white" />
      <Lashes x={149} y={111} dir={-1} />
    </>
  ),
  Sorprendida: (
    <>
      <path d="M146 99 Q156 93 166 99" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
      <circle cx="156" cy="118" r="11" fill="white" stroke={INK} strokeWidth="3" />
      <circle cx="156" cy="118" r="4.5" fill={INK} />
      <Lashes x={147} y={110} dir={-1} />
    </>
  ),
};

function ProfileBeak({ expression }) {
  const upper = (
    <>
      <path d="M181 125 L204 127 L181 133 Z" fill="#7A2F35" />
      <path d="M178 116 Q195 113 211 122 Q195 127 180 126 Z" {...BEAK} />
    </>
  );
  const lower = <path d="M180 131 Q194 132 206 137 Q194 142 178 139 Z" {...BEAK} />;

  let beak;
  if (expression === "Sorprendida") {
    beak = <>{upper}{lower}</>;
  } else if (expression === "Hablando") {
    beak = <>{upper}<g className="carpi-jaw-side">{lower}</g></>;
  } else {
    beak = (
      <>
        <path d="M178 118 Q195 116 211 127 Q195 137 178 135 Z" {...BEAK} />
        <path d="M183 127 Q196 127.5 207 127" fill="none" stroke="#C98A1E" strokeWidth="2" strokeLinecap="round" />
      </>
    );
  }

  // El pico va un poquito más abajo
  return <g transform="translate(0 6)">{beak}</g>;
}

function CarpiProfile({ expression }) {
  return (
    <svg
      className="carpi-bird"
      viewBox="0 0 240 290"
      role="img"
      aria-label={`Carpi de perfil, ${expression.toLowerCase()}`}
    >
      {/* Cola */}
      <path
        d="M76 214 Q42 236 34 258 Q56 252 66 242 Q62 258 72 264 Q82 246 94 228 Z"
        fill={INK}
      />

      {/* Patitas */}
      <g fill="none" stroke="#E9A13B" strokeWidth="5" strokeLinecap="round">
        <path d="M110 248 L108 266 M108 266 L100 270 M108 266 L116 270" />
        <path d="M132 248 L134 266 M134 266 L126 270 M134 266 L142 270" />
      </g>

      {/* Cuerpo y pancita */}
      <ellipse cx="117" cy="205" rx="56" ry="50" fill={INK} />
      <ellipse cx="142" cy="212" rx="28" ry="36" fill={CREAM} />
      <path
        d="M132 198 q4 5 8 0 M144 198 q4 5 8 0 M128 212 q4 5 8 0 M140 212 q4 5 8 0
           M152 212 q4 5 8 0 M134 226 q4 5 8 0 M146 226 q4 5 8 0"
        fill="none" stroke="#E8D5BD" strokeWidth="2" strokeLinecap="round"
      />

      {/* Ala con plumitas redondas atrás */}
      <g transform="rotate(-12 100 205)">
        <ellipse cx="57" cy="197" rx="12" ry="6.5" fill={WING} />
        <ellipse cx="54" cy="206" rx="12" ry="6.5" fill={WING} />
        <ellipse cx="58" cy="215" rx="12" ry="6.5" fill={WING} />
        <ellipse cx="100" cy="205" rx="40" ry="25" fill={WING} />
        <path
          d="M88 186 Q97 205 88 224 M108 184 Q118 205 108 226"
          fill="none" stroke={WING_LINE} strokeWidth="2" strokeLinecap="round"
        />
        <g fill={CREAM}>
          <circle cx="125" cy="198" r="2.5" />
          <circle cx="128" cy="211" r="2.5" />
          <circle cx="75" cy="205" r="2.5" />
        </g>
      </g>

      {/* Mechones de la nuca */}
      <ellipse cx="66" cy="132" rx="11" ry="7" fill={INK} transform="rotate(-20 66 132)" />
      <ellipse cx="72" cy="150" rx="11" ry="7" fill={INK} transform="rotate(25 72 150)" />

      {/* Cabeza, copete y gorrito */}
      <circle cx="128" cy="112" r="64" fill={INK} />
      <path d="M100 58 Q78 38 82 20 Q96 38 114 52 Z" fill={RED_DARK} />
      <path d="M112 52 Q106 26 122 12 Q124 34 134 48 Z" fill={RED} />
      <path d="M64 112 A64 64 0 0 1 192 112 Z" fill={RED} />

      {/* Carita */}
      <ellipse cx="146" cy="126" rx="42" ry="40" fill={CREAM} />

      {/* Plumitas y brillo del gorro */}
      <path
        d="M84 80 q5 4 10 0 M104 64 q5 4 10 0 M130 58 q5 4 10 0 M156 66 q5 4 10 0"
        fill="none" stroke="#C9353D" strokeWidth="2" strokeLinecap="round"
      />
      <path d="M82 70 Q96 56 112 54" fill="none" stroke="#FF8A80" strokeWidth="4" strokeLinecap="round" />

      {/* Cachete */}
      <ellipse cx="158" cy="144" rx="9" ry="5.5" fill="#FFB3AB" />

      {/* Ojo y pico */}
      {profileEyes[expression]}
      <ProfileBeak expression={expression} />

      {/* Extras */}
      {expression === "Sorprendida" && (
        <text x="200" y="92" fontSize="30" fontWeight="500" fill={RED}>!</text>
      )}
      {expression === "Hablando" && <SpeechBubble x={182} y={16} />}
    </svg>
  );
}

/* =====================================================
   COMPONENTE PRINCIPAL
   ===================================================== */

export default function Carpi() {
  const [view, setView] = useState("frente");
  const [expression, setExpression] = useState("Feliz");

  const changeView = (newView) => {
    setView(newView);
    // Si la expresión actual no existe en la otra vista, usamos la primera
    if (!VIEWS[newView].expressions.includes(expression)) {
      setExpression(VIEWS[newView].expressions[0]);
    }
  };

  return (
    <section className="carpi-app">
      <div className="carpi-views" role="group" aria-label="Vista de Carpi">
        {Object.entries(VIEWS).map(([key, { label }]) => (
          <button
            key={key}
            type="button"
            className={view === key ? "active" : ""}
            aria-pressed={view === key}
            onClick={() => changeView(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={`carpi-stage ${slug(expression)}`}>
        {view === "frente" ? (
          <CarpiFront expression={expression} />
        ) : (
          <CarpiProfile expression={expression} />
        )}

        {expression === "Dormida" && <span className="carpi-zzz">z z z</span>}
      </div>

      <h2>¡Hola, soy Carpi!</h2>
      <p className="carpi-subtitle">Tu pequeña compañera exploradora.</p>

      <div className="carpi-expressions" aria-label="Expresiones de Carpi">
        {VIEWS[view].expressions.map((item) => (
          <button
            key={item}
            type="button"
            className={expression === item ? "active" : ""}
            aria-pressed={expression === item}
            onClick={() => setExpression(item)}
          >
            {ICONS[item]} {item}
          </button>
        ))}
      </div>
    </section>
  );
}
/* ---------- Versión para usar dentro de la app (sin botones de demostración) ---------- */
export function CarpiMascota({ expresion = "Feliz", vista = "frente", tamano = 120 }) {
  return (
    <div
      className={`carpi-stage ${slug(expresion)}`}
      style={{ width: tamano, maxWidth: tamano, flexShrink: 0 }}
    >
      {vista === "frente" ? (
        <CarpiFront expression={expresion} />
      ) : (
        <CarpiProfile expression={expresion} />
      )}
      {expresion === "Dormida" && <span className="carpi-zzz">z z z</span>}
    </div>
  );
}
