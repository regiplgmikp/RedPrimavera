import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { createElement } from 'react';
import { createRoot } from 'react-dom/client';
import Carpi from './components/Carpi.jsx';

// Recorrido guiado. Cada paso señala un elemento de la página y Carpi lo explica.
export function iniciarRecorrido() {
  // Una pose por paso, en el mismo orden que los pasos de abajo. Cámbialas a tu gusto.
const POSES_PASOS = [
  'presentando', // 1 ¡Vamos!
  'senalando',   // 2 Tamaño de los hexágonos
  'senalando',   // 3 Vulnerabilidad
  'curiosa',     // 4 ¿Buscas a alguien?
  'sorprendida', // 5 Ojo con este botón
  'senalando',   // 6 Qué pinta el mapa
  'hablando',    // 7 El mapa
  'hablando',    // 8 El grafo
  'curiosa',     // 9 ¿Dudas?
  'hola',        // 10 Volver a empezar
];

let raizCarpi = null;

function quitarCarpi() {
  if (raizCarpi) {
    const vieja = raizCarpi;
    raizCarpi = null;
    setTimeout(() => vieja.unmount(), 0);
  }
}

function ponerCarpi(popover, indice) {
  quitarCarpi();
  popover.wrapper.querySelector('.recorrido-figura')?.remove();
  const figura = document.createElement('div');
  figura.className = 'recorrido-figura';
  popover.title.before(figura);
  raizCarpi = createRoot(figura);
  raizCarpi.render(createElement(Carpi, { pose: POSES_PASOS[indice] || 'hola', tamano: 87 }));
}
  const recorrido = driver({
    showProgress: true,
    progressText: 'Paso {{current}} de {{total}}',
    nextBtnText: 'Siguiente →',
    prevBtnText: '← Atrás',
    doneBtnText: '¡Listo!',
    allowClose: true,
    overlayOpacity: 0.55,
    stagePadding: 6,
    popoverClass: 'recorrido-carpi',onPopoverRender: (popover) => ponerCarpi(popover, recorrido.getActiveIndex()),
    onDestroyed: () => quitarCarpi(),
    steps: [
      { element: '.estado', popover: { title: '¡Vamos!', side: 'bottom', align: 'end',
        description: 'Aquí arriba te cuento cuántos hexágonos (celdas) estás viendo y de qué tamaño son.' } },
      { element: '#resolucion', popover: { title: 'Tamaño de los hexágonos', side: 'right',
        description: 'Los de resolución 8 abarcan todo el bosque; los de 9 son más chiquitos y tienen más detalle.' } },
      { element: '#ivc_min', popover: { title: 'Vulnerabilidad a incendios', side: 'right',
        description: 'Aquí filtras por el índice de vulnerabilidad. Prueba con 0.6 para ver solo las zonas más delicadas.' } },
      { element: '#buscar-especie', popover: { title: '¿Buscas a alguien?', side: 'right',
        description: 'Escribe «carpintero» y verás en qué zonas lo han visto. ¡Yo soy fan!' } },
      { element: 'aside .primario', popover: { title: 'Ojo con este botón', side: 'right',
        description: 'Los filtros solo se aplican cuando lo pulsas.' } },
      { element: '#colorMapa', popover: { title: 'Qué pinta el mapa', side: 'right',
        description: 'Vulnerabilidad, incendios, vegetación, observaciones… tú eliges qué característica ver.' } },
      { element: '.paneles > :nth-child(1)', popover: { title: 'El mapa', side: 'top', align: 'center',
        description: 'Cada hexágono es una zona del bosque. Si tocas uno, el grafo te muestra las especies que se han visto ahí.' } },
      { element: '.paneles > :nth-child(2)', popover: { title: 'El grafo', side: 'left', align: 'center',
        description: 'Cada punto es una especie y las líneas unen a las que suelen verse en las mismas zonas. Toca una y el mapa ilumina dónde se ha visto.' } },
      { element: '.ayuda-mini', popover: { title: '¿Dudas?', side: 'right',
        description: 'Estos signos de interrogación te explican cada filtro con palabras sencillas.' } },
      { element: '.ayuda-btn', popover: { title: 'Volver a empezar', side: 'bottom', align: 'end',
        description: 'Este botón abre otra vez mi bienvenida, y desde ahí puedes repetir el recorrido.' } },
    ],
  });
  recorrido.drive();
}