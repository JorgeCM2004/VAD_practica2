window.vadMapa = {
  soltarMonigote: function (evento, contexto) {
    const posicion = evento.target.getLatLng();
    contexto.setProps({ position: [posicion.lat, posicion.lng] });
  },
};
