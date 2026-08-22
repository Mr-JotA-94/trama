// TRAMA — web/app/components/ModalDia.js
// ÚNICO Client Component del expediente. Excepción consciente al principio cero-JS.
//
// POR QUÉ SE ROMPE EL PRINCIPIO ACÁ Y NO EN OTRO LADO:
// el resto de los colapsos del sitio son <details>, que despliegan EN SITIO y no
// atrapan al usuario. Un modal sí lo atrapa: tapa la página y hay que saber salir.
// Un modal hecho con :target o con el truco del checkbox no tiene tecla Escape, no
// atrapa el foco del teclado y no es anunciado como diálogo por un lector de
// pantalla. Para un elemento que BLOQUEA la lectura, la accesibilidad de teclado es
// load-bearing, no cosmética. <dialog>.showModal() da Escape, trampa de foco,
// ::backdrop, inert del fondo y semántica ARIA gratis, nativos del navegador.
//
// Recibe `children` YA RENDERIZADO EN EL SERVIDOR (RSC payload): este archivo no
// sabe nada de resumenes_dia ni consulta nada. Solo abre y cierra una caja.

"use client";

import { useEffect, useRef, useState } from "react";

export default function ModalDia({
  etiquetaBoton,     // texto del disparador, ej. "Hechos del día"
  tituloModal,       // encabezado dentro del modal, ej. "Jueves 18 de julio"
  claseBoton = "dia-boton",
  children,
}) {
  const ref = useRef(null);
  const [abierto, setAbierto] = useState(false);

  // Abrir/cerrar el <dialog> de verdad. Se hace en un efecto y no en el onClick
  // para que el estado de React sea la única fuente de verdad: si el diálogo se
  // cierra por Escape (evento nativo), el estado se entera por onClose y no queda
  // desincronizado.
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  // El fondo no debe hacer scroll mientras el modal está abierto. showModal() hace
  // inerte el fondo (no se puede tabular ni clicar) pero NO congela el scroll.
  useEffect(() => {
    if (!abierto) return;
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previo; };
  }, [abierto]);

  // ── El botón ATRÁS cierra el modal, no la página ──────────────────────────
  // Es el problema concreto que motivó esta pieza: una ventana emergente PARECE
  // una página nueva, el reflejo es dar atrás, y con un modal común eso te saca
  // del expediente. Empujamos una entrada de historial al abrir; el atrás la
  // consume y solo cierra el modal.
  //
  // La limpieza distingue los dos caminos de cierre:
  //   - cerrado POR atrás: la entrada ya no existe -> history.state es null -> no
  //     tocamos nada (si hiciéramos back() acá, saldríamos de la página: el bug
  //     que estamos evitando, al revés).
  //   - cerrado por botón o Escape: la entrada sigue puesta -> la retiramos, para
  //     no dejar basura en el historial que obligue a dar atrás dos veces.
  // La URL no cambia (mismo href), así que el router de Next no navega a ningún lado.
  useEffect(() => {
    if (!abierto) return;
    window.history.pushState({ modalTrama: true }, "", window.location.href);
    const alVolver = () => setAbierto(false);
    window.addEventListener("popstate", alVolver);
    return () => {
      window.removeEventListener("popstate", alVolver);
      if (window.history.state?.modalTrama) window.history.back();
    };
  }, [abierto]);

  // Clic en el fondo oscuro. El <dialog> recibe el evento cuando el punto clicado
  // cae fuera de su caja de contenido; por eso comparamos contra el nodo mismo.
  function clicEnFondo(e) {
    if (e.target === ref.current) setAbierto(false);
  }

  return (
    <>
      <button
        type="button"
        className={claseBoton}
        onClick={() => setAbierto(true)}
      >
        {etiquetaBoton}
      </button>

      <dialog
        ref={ref}
        className="modal-dia"
        onClose={() => setAbierto(false)}
        onClick={clicEnFondo}
        aria-labelledby="modal-dia-titulo"
      >
        <div className="modal-dia-caja">
          {/* Encabezado pegajoso: el cierre queda a la vista aunque el contenido
              del día sea largo y haya que hacer scroll dentro del modal. */}
          <div className="modal-dia-header">
            <h2 className="modal-dia-titulo" id="modal-dia-titulo">{tituloModal}</h2>
            <button
              type="button"
              className="modal-dia-cerrar"
              onClick={() => setAbierto(false)}
              autoFocus
            >
              <span aria-hidden="true">✕</span> Cerrar
            </button>
          </div>

          <div className="modal-dia-cuerpo">{children}</div>

          {/* Segundo cierre al final: si el día fue denso, quien terminó de leer
              está abajo y no debería tener que volver arriba para salir. */}
          <div className="modal-dia-pie">
            <button
              type="button"
              className="modal-dia-cerrar-ancho"
              onClick={() => setAbierto(false)}
            >
              Cerrar
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
