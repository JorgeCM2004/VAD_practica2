from src.aplicacion import CuadroDeMando

app = CuadroDeMando().app
server = app.server

if __name__ == "__main__":
    app.run(debug=True, dev_tools_ui=False)
