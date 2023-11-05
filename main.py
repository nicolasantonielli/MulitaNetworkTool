from PlacaRed import PlacaRed
from MenuSuperior import MenuSuperior
import json
import subprocess
from ttkbootstrap import Style
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.constants import *
import ttkbootstrap as ttk
from tkinter import *
from PIL import Image

Image.CUBIC = Image.BICUBIC

# Modulo Sensor de temperatura
# 3#import Adafruit_DHT
# 3#SENSOR_DHT = Adafruit_DHT.DHT11
# 3#PIN_DHT = 4

###########################
#### Ventana Principal ####
###########################

root = ttk.Window(title='RED TEST', themename="cosmo")
root.geometry('800x480')
root.resizable(False, False)
# root.wm_attributes('-fullscreen','True')


###########  Fin Seccion Ventana Principal  #####################

# Variables globales a eliminar
contadorDump = 0
contadorNetDiscover = 0
uploadBps = 0
downloadBps = 0
ejecutandoPing = FALSE


#################
#### Estilos ####
#################

style = Style()
style.theme_use("cosmo")


def aplicarEstilos():

    # Botones Home

    style = ttk.Style()
    style.configure(
        'myhome.primary.Outline.TButton',
        font=(
            'helvetica',
            18),
        padding=53,
        width=20,
        relief=ttk.RAISED,
        borderwidth=4)

    # Botones

    style = ttk.Style()
    style.configure('custom.success.TButton', font=('helvetica', 15))
    style.configure('custom.primary.TButton', font=('helvetica', 15))
    style.configure('custom.danger.TButton', font=('helvetica', 15))
    style.configure(
        'barraSuperior.primary.TButton', font=(
            'helvetica', 15), padding=8)
    style.configure(
        'barraSuperior.danger.TButton', font=(
            'helvetica', 15), padding=8)
    style.configure(
        'barraSuperior.success.TButton', font=(
            'helvetica', 15), padding=8)

    # Pestañas
    style.configure('my.primary.TNotebook.Label', font=('helvetica', 18))

    # Estilos frame destino

    style.configure(
        'destino.success.TButton',
        font=(
            'helvetica',
            14),
        padding=7,
        width=15)
    style.configure(
        'destino.danger.TButton',
        font=(
            'helvetica',
            14),
        padding=7,
        width=15)
    style.configure('destino.TLabel', font=('helvetica', 14), padding=7)


# Inicializacion de estilos
aplicarEstilos()

##########################################  Fin Seccion Estilos  #########

##########################################################################

###################
#### Pantallas ####
###################

home = ttk.Frame(root)
dump = ttk.Frame(root)
mtr = ttk.Frame(root)
tap = ttk.Frame(root)
escaneo = ttk.Frame(root)
config = ttk.Frame(root)
tools = ttk.Frame(root)

home.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
dump.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
mtr.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
tap.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
escaneo.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
config.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)
tools.grid(row=0, column=0, sticky='nsew', padx=0, pady=10)

##########################################  Fin Seccion Pantallas  #######

##########################################################################

######################
#### Ventana Home ####
######################

# Titulo

ttk.Button(home, text='CAPTURA PAQUETES', style='myhome.primary.Outline.TButton',
           command=lambda: dump.tkraise()).grid(row=1, column=0, padx=17, pady=5)

ttk.Button(home, text='TRAZAS', style='myhome.primary.Outline.TButton',
           command=lambda: mtr.tkraise()).grid(row=1, column=1)

ttk.Button(home, text='TAP', style='myhome.primary.Outline.TButton',
           command=lambda: tap.tkraise()).grid(row=2, column=0, pady=10)

ttk.Button(home, text='ESCANEO', style='myhome.primary.Outline.TButton',
           command=lambda: escaneo.tkraise()).grid(row=2, column=1)

ttk.Button(home, text='HERRAMIENTAS', style='myhome.primary.Outline.TButton',
           command=lambda: tools.tkraise()).grid(row=3, column=0)

ttk.Button(home, text='CONFIG', style='myhome.primary.Outline.TButton',
           command=lambda: config.tkraise()).grid(row=3, column=1, pady=10)


##########################################  Fin Seccion Home  ############

# Funcion de share

iconShare = PhotoImage(file='./img/sharethis-32.png')


def shareResultado():
    print(f'Funcion share')

##########################################################################

######################
#### Ventana Dump ####
######################


def interfaceDump():

    global contadorDump
    if contadorDump % 2 == 0:

        # subprocess.Popen('mount /dev/sda1 /media/usb', stdout=subprocess.PIPE,shell=True)

        botonDump['text'] = 'DETENER'
        botonDump.configure(style='custom.danger.TButton')
        comandoDump = f'/bin/tcpdump -Q {seleccionDireccion.get()} -i {seleccionInterface.get()} -w /root/Desktop/ {textArchivoDump.get()}.pcap'
        print(comandoDump)
        subprocess.Popen(comandoDump, stdout=subprocess.PIPE, shell=True)
        contadorDump += 1

    else:
        botonDump['text'] = 'INICIAR'
        botonDump.configure(style='custom.success.TButton')
        comandoDump = 'killall tcpdump'
        subprocess.Popen(comandoDump, stdout=subprocess.PIPE, shell=True)
        contadorDump += 1

# Frame Titulo


tituloFrameDump = ttk.Frame(dump)
tituloFrameDump.pack(fill=BOTH)

# Objeto menuSuperior
menuDump = MenuSuperior(tituloFrameDump, 'CAPTURA DE PAQUETES', home)

# Agregar boton Compartir
menuDump.agregarBotonSuperior(
    tituloFrameDump,
    shareResultado,
    'SHARE', iconShare)

# Frame Seleccion de interface
frameInterface = ttk.Frame(dump)
frameInterface.pack(padx=10, pady=30, fill=BOTH)

interface = PlacaRed()
interfaces = interface.tomarInterface()
interfacesLinux = interface.tomarInterface()

# interfaces = ['Interna', 'Ext. A', 'Ext. B', 'WiFi']
# interfacesLinux = ['eth0', 'eth1', 'eth2', 'wlan0']

seleccionInterface = StringVar()
textoLabelFrameInterface = Label(text='Seleccion de interface')
labelFrameInterface = ttk.Labelframe(
    frameInterface,
    text='Seleccion de Interface',
    padding=5)

labelFrameInterface.pack(pady=5, side='left')
i = 0

for interface1 in interfaces:
    ttk.Radiobutton(labelFrameInterface, style='my.primary.TRadiobutton', variable=seleccionInterface,
                    text=interface1, value=interfacesLinux[i]).pack(pady=15, padx=8, side='left')

    # iterador de lista de interfaces linux
    i = i + 1

# Seleccion entrante o saliente

direcciones = ['Entrante', 'Saliente', 'Entrante y Saliente']
direccionesLinux = ['in', 'out', 'inout']

seleccionDireccion = StringVar()

labelFrameDireccion = ttk.Labelframe(
    frameInterface, text='Seleccion de dirección', padding=5)

labelFrameDireccion.pack(pady=5, padx=10, side='left')

j = 0

for direccion in direcciones:
    ttk.Radiobutton(labelFrameDireccion, style='my.primary.TRadiobutton', variable=seleccionDireccion,
                    text=direccion, value=direccionesLinux[j]).pack(pady=15, padx=8, side='left')

    # iterador de lista de interfaces linux
    j = j + 1


# Frame Archivo

frameArchivo = ttk.Frame(dump)
frameArchivo.pack(padx=5, pady=10, fill=BOTH)

labelFrameArchivo = ttk.Labelframe(
    frameArchivo,
    text='Nombre de archivo',
    padding=5)
labelFrameArchivo.pack(pady=5, side='left')


textArchivoDump = ttk.Entry(labelFrameArchivo, width=25, font=('Courier', 13))
textArchivoDump.insert(END, 'prueba')
textArchivoDump.pack()

# Frame Control

frameControl = ttk.Frame(dump)
frameControl.pack(padx=5, pady=20, fill=BOTH)


# Boton de comando
botonDump = ttk.Button(frameControl, text='INICIAR',
                       style='custom.success.TButton', padding=10, width=15, command=interfaceDump)
botonDump.pack(padx=20, pady=10, side='right')


##########################################  Fin Seccion Dump  ############

##########################################################################

########################
#### Ventana Trazas ####
########################

def funcionMtr():

    resultadoMtr.delete(1.0, END)
    resultadoMtr.update()
    resultadoMtr.insert(END, 'Trazando...Aguarde por favor\n')
    resultadoMtr.update()
    comandoMtr = f'/bin/mtr {textTargetMtr.get()} -nrc 6'
    p3 = subprocess.Popen(comandoMtr, stdout=subprocess.PIPE,
                          universal_newlines=True, shell=True)
    while p3.poll() is None:
        resultadoMtr.update()
        resultadoMtr.insert(END, p3.stdout.read())
    p3.terminate()


# Titulo
tituloFrameMtr = ttk.Frame(mtr)
tituloFrameMtr.pack(fill=BOTH)

# Objeto menuSuperior

menuMtr = MenuSuperior(tituloFrameMtr, 'TRAZAS', home)

# Agregar boton Compartir
menuMtr.agregarBotonSuperior(
    tituloFrameMtr,
    shareResultado,
    'SHARE', iconShare)

# Frame de pestañas

frameNoteMtr = ttk.Notebook(mtr, style='primary')
frameNoteMtr.pack(padx=10, pady=2, fill=BOTH)
tabMtr1 = ttk.Frame(frameNoteMtr)
tabMtr2 = ttk.Frame(frameNoteMtr)

# Pestaña Mtr

# Frame Cuadro destino

destinoFrameMtr = Frame(tabMtr1)
destinoFrameMtr.pack(fill=BOTH, pady=2)
ttk.Button(destinoFrameMtr, text='TRAZADO', style='destino.success.TButton',
           command=funcionMtr).pack(padx=23, pady=10, side='right')

textTargetMtr = ttk.Entry(destinoFrameMtr, width=34, font=('Courier', 15))
textTargetMtr.pack(pady=10, side='right')

ttk.Label(destinoFrameMtr, text='IP DESTINO',
          style='destino.TLabel').pack(side='right')

# Frame de respuesta

resultadoFrameMtr = Frame(tabMtr1, height=15, width=80)
resultadoFrameMtr.pack(pady=2, padx=5)

# Cuadro de texto resultado

resultadoMtr = Text(resultadoFrameMtr, height=15,
                    width=80, font=('Courier', 11))
resultadoMtr.pack(fill=BOTH)

procesoPing = None

def funcionPing(count, velo, bytes):
    global ejecutandoPing
    global procesoPing

    if ejecutandoPing == FALSE:

        ejecutandoPing = TRUE

        botonIniciarPing['text'] = 'DETENER'
        botonIniciarPing.configure(style='custom.danger.TButton')
        resultadoPing.delete(1.0, END)
        if int(count) != 0:
            comandoPing = f'/bin/ping {textTargetPing.get()} -n -c {int(count)} -i {velo:.2f} -s {int(bytes)}'
        elif int(count) == 0:
            comandoPing = f'/bin/ping {textTargetPing.get()} -n -i {velo:.2f} -s {int(bytes)}'
        

        procesoPing = subprocess.Popen(comandoPing, stdout=subprocess.PIPE,
                                universal_newlines=True, shell=True, bufsize=0)
        while procesoPing.poll() is None:
            resultadoPing.update()
            resultadoPing.insert(END, procesoPing.stdout.readline())
        procesoPing.terminate()

        for i in range(4):
            resultadoPing.insert(END, procesoPing.stdout.readline())
            resultadoPing.update()

            
        botonIniciarPing['text'] = 'INICIAR'
        botonIniciarPing.configure(style='custom.success.TButton')

        ejecutandoPing = FALSE
    
    elif ejecutandoPing == TRUE:
        botonIniciarPing['text'] = 'INICIAR'
        botonIniciarPing.configure(style='custom.success.TButton')

        subprocess.Popen.kill(procesoPing)

        #for i in range(4):
        #    resultadoPing.insert(END, procesoPing.stdout.readline())
        #    resultadoPing.update()
        
        comandoPing = 'pkill -2 ping'
        subprocess.Popen(comandoPing, stdout=subprocess.PIPE, shell=True)
        ejecutandoPing = FALSE
        
def pingScaler(e):
    countLabel.config(text=f'{int(countScale.get())} envios') 
    velocidadLabel.config(text=f'{velocidadScale.get():.1f} segundos') 
    bytesLabel.config(text=f'{int(bytesScale.get())} bytes')

# Pestaña Ping


# Frame Cuadro destino
destinoFramePing = Frame(tabMtr2, width=80)
destinoFramePing.pack(fill=BOTH, pady=2)

botonIniciarPing = ttk.Button(destinoFramePing, text='PING', style='destino.success.TButton',
           command=lambda:funcionPing(countScale.get(),velocidadScale.get(),bytesScale.get()))
botonIniciarPing.pack(padx=23, pady=10, side='right')

textTargetPing = ttk.Entry(destinoFramePing, width=34, font=('Courier', 15))
textTargetPing.pack(pady=10, side='right')

ttk.Label(destinoFramePing, text='IP DESTINO',
          style='destino.TLabel').pack(side='right')




# Frame de configuracion

frameConfig = Frame(tabMtr2)
frameConfig.pack(pady=2, padx=5)


frameCountScale = Frame(frameConfig)
frameCountScale.pack(side='left', padx=10)
countScale = ttk.Scale(frameCountScale, length=200, orient='horizontal',from_=0, to=20, state='enable', command=pingScaler)
countScale.set(4)
countScale.pack()
countLabel = ttk.Label(frameCountScale,text=f'{int(countScale.get())} envios')
countLabel.pack()

frameVelocidadScale = Frame(frameConfig)
frameVelocidadScale.pack(side='left', padx=10)
velocidadScale = ttk.Scale(frameVelocidadScale, length=200, orient='horizontal',from_=0, to=1, state='enable', command=pingScaler)
velocidadScale.set(1)
velocidadScale.pack()
velocidadLabel = ttk.Label(frameVelocidadScale,text=f'{velocidadScale.get():.1f} segundos')
velocidadLabel.pack()

frameBytesScale = Frame(frameConfig)
frameBytesScale.pack(side='left', padx=10)
bytesScale = ttk.Scale(frameBytesScale, length=200, orient='horizontal',from_=0, to=1024, state='enable', command=pingScaler)
bytesScale.set(64)
bytesScale.pack()
bytesLabel = ttk.Label(frameBytesScale,text=f'{int(bytesScale.get())} bytes')
bytesLabel.pack()

# Frame de respuesta

resultadoFramePing = Frame(tabMtr2, height=15, width=80)
resultadoFramePing.pack(pady=2, padx=5)

# Cuadro de texto resultado

resultadoPing = Text(resultadoFramePing, height=15,
                     width=80, font=('Courier', 11))
resultadoPing.pack(fill=BOTH)


# Fin Pestañas

frameNoteMtr.add(tabMtr1, text='Trazas')
frameNoteMtr.add(tabMtr2, text='Ping')

###############################################  Fin Seccion Trazas  #####

#####################
#### Ventana Tap ####
#####################

# Funcion de recarga de interfaces


def refrezcarInterfaces():
    print(f'Funcion Refrezcar')


# Titulo
tituloFrameTap = ttk.Frame(tap)
tituloFrameTap.pack(fill=BOTH)

# Objeto menuSuperior
menuTap = MenuSuperior(tituloFrameTap, 'TAP', home)

# Agregar boton Refresh
iconSincroEth = PhotoImage(file='./img/refresh-32.png')
menuTap.agregarBotonSuperior(
    tituloFrameTap,
    refrezcarInterfaces,
    'Refresh', iconSincroEth)

# Agregar boton Compartir
menuTap.agregarBotonSuperior(
    tituloFrameTap,
    shareResultado,
    'SHARE', iconShare)

# Frame de pestañas
frameNoteTap = ttk.Notebook(tap, style='primary')
frameNoteTap.pack(padx=10, pady=2, fill=BOTH)

tabTap1 = ttk.Frame(frameNoteTap)
tabTap2 = ttk.Frame(frameNoteTap)

# Refrescar Interfaces
interface = PlacaRed()
interfaces = interface.tomarInterface()
interfacesLinux = interface.tomarInterface()

# Frame Seleccion de Interface Entrante
frameInterfaceEntrante = ttk.Frame(tabTap1)
frameInterfaceEntrante.pack(padx=5, pady=8, fill=BOTH)

seleccionInterfaceEntrante = StringVar()

labelFrameInterfaceEntrante = ttk.Labelframe(
    frameInterfaceEntrante, text='Seleccion de interface Entrante', padding=5)

labelFrameInterfaceEntrante.pack(pady=5, side='left')
i = 0

for interface1 in interfaces:
    ttk.Radiobutton(labelFrameInterfaceEntrante, style='my.primary.TRadiobutton', variable=seleccionInterfaceEntrante,
                    text=interface1, value=interfacesLinux[i]).pack(pady=10, padx=8, side='left')
    # iterador de lista de interfaces linux
    i = i + 1

# Frame Seleccion de Interface Mirror
frameInterfaceMirror = ttk.Frame(tabTap1)
frameInterfaceMirror.pack(padx=5, pady=8, fill=BOTH)

seleccionInterfaceMirror = StringVar()

labelFrameInterfaceMirror = ttk.Labelframe(
    frameInterfaceMirror, text='Seleccion de interface Mirror', padding=5)

labelFrameInterfaceMirror.pack(pady=5, side='left')
i = 0

for interface2 in interfaces:
    ttk.Radiobutton(labelFrameInterfaceMirror, style='my.primary.TRadiobutton', variable=seleccionInterfaceMirror,
                    text=interface2, value=interfacesLinux[i]).pack(pady=10, padx=8, side='left')
    # iterador de lista de interfaces linux
    i = i + 1


# Frame Seleccion de Interface Saliente

frameInterfaceSaliente = ttk.Frame(tabTap1)
frameInterfaceSaliente.pack(padx=5, pady=5, fill=BOTH)

seleccionInterfaceSaliente = StringVar()

labelFrameInterfaceSaliente = ttk.Labelframe(
    frameInterfaceSaliente, text='Seleccion de interface Saliente', padding=5)

labelFrameInterfaceSaliente.pack(pady=5, side='left')
i = 0

for interface2 in interfaces:
    ttk.Radiobutton(labelFrameInterfaceSaliente, style='my.primary.TRadiobutton', variable=seleccionInterfaceSaliente,
                    text=interface2, value=interfacesLinux[i]).pack(pady=10, padx=8, side='left')
    # iterador de lista de interfaces linux
    i = i + 1


botonTap = ttk.Button(
    tabTap1,
    text='INICIAR',
    style='custom.success.TButton',
    padding=10,
    width=15,
    command=interfaceDump)
botonTap.pack(padx=20, pady=2)

# Frame Cuadro destino
destinoFrameTap = Frame(tabTap2)
destinoFrameTap.pack(fill=BOTH, pady=2)

# Frame de respuesta
resultadoFrameTap = Frame(tabTap2)
resultadoFrameTap.pack(pady=2, padx=5, fill=BOTH)

# Cuadro de texto resultado
resultadoTap = Text(resultadoFrameTap, font=('Courier', 11))
resultadoTap.pack(fill=BOTH)

# Creacion de pestañas
frameNoteTap.add(tabTap1, text='Configuracion')
frameNoteTap.add(tabTap2, text='Pantalla')

##########################################  Fin Seccion Tap  #############

#########################
#### Ventana Escaneo ####
#########################
j9re = 0

def funcionNmap():

    resultadoEscaneo.delete(1.0, END)
    comandoNmap = '/bin/nmap ' + textTargetEscaneo.get() + ''
    textoNmap = subprocess.run(
        [comandoNmap], shell=True, capture_output=True, text=True)
    textoResultanteNmap = textoNmap.stdout
    resultadoEscaneo.insert(END, str(textoResultanteNmap))


def funcionDiscover():
    global j9re
    global contadorNetDiscover
    if contadorNetDiscover % 2 == 0:
        botonDescubrir.configure(
            text='DETENER', style='destino.danger.TButton')
        resultadoDiscover.delete(1.0, END)
        comandoDiscover = '/sbin/netdiscover -fP'

        # p1 = subprocess.Popen(
        # comandoDiscover, stdout=subprocess.PIPE, bufsize=0,
        # universal_newlines=True, shell=True)

        p1 = subprocess.Popen(comandoDiscover, stdout=subprocess.PIPE,
                              bufsize=0, universal_newlines=True, shell=True)

        while p1.poll() is None:

            resultadoDiscover.insert(END, p1.stdout.readline())
            resultadoDiscover.update()
            j9re +=1
            print (j9re)


        p1.stdout.close()
        #p1.wait()

        contadorNetDiscover += 1

    else:
        subprocess.run('killall netdiscover', shell=True)
        p1.kill()
        botonDescubrir.configure(
            text='DESCUBRIMIENTO IP',
            style='destino.success.TButton')
        contadorNetDiscover += 1


# Frame Titulo
tituloFrameEscaneo = ttk.Frame(escaneo)
tituloFrameEscaneo.pack(fill=BOTH)


# Objeto menuSuperior
menuEscaneo = MenuSuperior(tituloFrameEscaneo, 'ESCANEO', home)

# Agregar boton Compartir
menuEscaneo.agregarBotonSuperior(
    tituloFrameEscaneo,
    shareResultado,
    'SHARE', iconShare)

# Frame de pestañas

frameNoteEscaneo = ttk.Notebook(escaneo, bootstyle='primary')
frameNoteEscaneo.pack(padx=10, pady=2, fill=BOTH)

tabEscaneo1 = ttk.Frame(frameNoteEscaneo)
tabEscaneo2 = ttk.Frame(frameNoteEscaneo)


# Pestaña Escaneo

# Frame Cuadro destino

destinoFrameEscaneo = Frame(tabEscaneo1)
destinoFrameEscaneo.pack(pady=2, fill=BOTH)

ttk.Button(destinoFrameEscaneo, text='ESCANEAR', style='destino.success.TButton',
           command=funcionNmap).pack(padx=23, pady=10, side='right')


textTargetEscaneo = ttk.Entry(
    destinoFrameEscaneo, width=34, font=(
        'Courier', 15))
textTargetEscaneo.pack(pady=10, side='right')

ttk.Label(
    destinoFrameEscaneo,
    text='IP DESTINO',
    style='destino.TLabel').pack(
        side='right')


# Frame de respuesta
resultadoFrameEscaneo = Frame(tabEscaneo1, height=15, width=80)
resultadoFrameEscaneo.pack(pady=2, padx=5)

# Cuadro de texto resultado

resultadoEscaneo = Text(
    resultadoFrameEscaneo,
    height=15,
    width=80,
    font=(
        'Courier',
        11))
resultadoEscaneo.pack(fill=BOTH)

# Pestaña Descubrimiento

# Frame Cuadro destino

destinoFrameDiscover = Frame(tabEscaneo2, width=80)
destinoFrameDiscover.pack(pady=2, padx=2)

botonDescubrir = ttk.Button(destinoFrameDiscover, text='DESCUBRIMIENTO IP', padding=10, style='destino.success.TButton',
                            width=20, command=funcionDiscover)
botonDescubrir.pack(padx=20, pady=10, side='right')

# Frame de respuesta

resultadoFrameDiscover = Frame(tabEscaneo2, height=15, width=80)
resultadoFrameDiscover.pack(pady=2, padx=5)


# Cuadro de texto resultado

resultadoDiscover = Text(
    resultadoFrameDiscover,
    height=15,
    width=80,
    font=(
        'Courier',
        11))
resultadoDiscover.pack(fill=BOTH)


# Fin Pestañas

frameNoteEscaneo.add(tabEscaneo1, text='Escaneo de puertos')
frameNoteEscaneo.add(tabEscaneo2, text='Descubrimiento IP')


##########################################  Fin Seccion Escaneo  #########

########################
#### Ventana Config ####
########################

# Titulo
tituloFrameConfig = ttk.Frame(config)
tituloFrameConfig.pack(fill=BOTH)

# Objeto menuSuperior
menuConfig = MenuSuperior(tituloFrameConfig, 'CONFIGURACIÓN', home)

# Pestañas
frameNoteConfig = ttk.Notebook(config, bootstyle='primary')
frameNoteConfig.pack(padx=10, pady=2, fill=BOTH)

tabConfig1 = ttk.Frame(frameNoteConfig)
tabConfig2 = ttk.Frame(frameNoteConfig)
tabConfig3 = ttk.Frame(frameNoteConfig)
tabConfig4 = ttk.Frame(frameNoteConfig)
tabConfig5 = ttk.Frame(frameNoteConfig)

# Pestaña General


def cambiarEstilo(x):
    estilo = x
    style.theme_use(estilo)
    aplicarEstilos()


seleccionEstilos = ttk.Menubutton(
    tabConfig1,
    text='ESTILO',
    bootstyle='primary')
seleccionEstilos.pack(pady=15)


estilos = ['cosmo', 'darkly', 'pulse', 'lumen', 'litera',
           'journal', 'solar', 'superhero', 'vapor', 'cyborg']


menuEstilos = ttk.Menu(seleccionEstilos, font=('helvetica', 18))

items = StringVar()

for x in estilos:
    menuEstilos.add_radiobutton(
        label=x, variable=items, command=lambda x=x: cambiarEstilo(x))


seleccionEstilos['menu'] = menuEstilos

generalAplicar = ttk.Button(
    tabConfig1,
    text='APLICAR',
    style='destino.success.TButton',
    command=cambiarEstilo)
generalAplicar.pack(pady=20)


# Pestaña Wifi

wifiAplicar = ttk.Button(tabConfig2, text='APLICAR',
                         style='destino.success.TButton', command=lambda: home.tkraise())
wifiAplicar.pack(pady=20)


# Pestaña Ethernet Interna

internalAplicar = ttk.Button(
    tabConfig3,
    text='APLICAR',
    style='destino.success.TButton',
    command=lambda: home.tkraise())
internalAplicar.pack(pady=20)


# Pestaña Ethernet Externa

enternalAplicar = ttk.Button(
    tabConfig4,
    text='APLICAR',
    style='destino.success.TButton',
    command=lambda: home.tkraise())
enternalAplicar.pack(pady=20)


# Pestaña Mantenimiento
mantenimeintoSalir = ttk.Button(
    tabConfig5,
    text='Cerrar APP',
    style='destino.danger.TButton',
    command=lambda: root.destroy())
mantenimeintoSalir.pack(pady=20)

frameNoteConfig.add(tabConfig1, text='General')
frameNoteConfig.add(tabConfig2, text='Wifi')
frameNoteConfig.add(tabConfig3, text='Ethernet Interna')
frameNoteConfig.add(tabConfig4, text='Ethernet Externa')
frameNoteConfig.add(tabConfig5, text='Mantenimiento')

##########################################  Fin Seccion Escaneo  #########

##############################
#### Ventana Herramientas ####
##############################


def tomarTemperatura():
    humedad, temperatura = 50, 26  # 3#Adafruit_DHT.read(SENSOR_DHT, PIN_DHT)
    humedad = humedad + 15
    temperatura = temperatura - 6

    if humedad is not None and temperatura is not None:
        temp = 'Temperatura: ' + str(temperatura) + '°c'
        hum = 'Humedad: ' + str(humedad) + '%'
        tempLabel.config(text=temp)
        humLabel.config(text=hum)


def funcionWol():

    resultadoWol.delete(1.0, END)
    comandoWol = '/bin/wakeonlan ' + textTargetWol.get() + ''
    textoWol = subprocess.run(
        [comandoWol], shell=True, capture_output=True, text=True)
    textoResultanteWol = textoWol.stdout
    resultadoWol.insert(END, str(textoResultanteWol))


def funcionSpeedTest():

    print('entre en la funcion\n')
    global downloadBps
    global uploadBps
    comandoSpeedTest = '/bin/speedtest --json'

    p = subprocess.Popen(
        comandoSpeedTest, stdout=subprocess.PIPE, shell=True)
    resultado = p.stdout.read()

    print(f'{resultado}')

    resultadoJson = json.loads(resultado)
    downloadBps = resultadoJson["download"]
    uploadBps = resultadoJson["upload"]
    print(f'Upload: {uploadBps:.2f} Mbps')
    print(f'Download: {downloadBps:.2f} Mbps')


# Titulo
tituloFrameTools = ttk.Frame(tools)
tituloFrameTools.pack(fill=BOTH)

# Objeto menuSuperior
menuTools = MenuSuperior(tituloFrameTools, 'HERRAMIENTAS', home)

# Agregar boton Compartir
menuTools.agregarBotonSuperior(
    tituloFrameTools,
    shareResultado,
    'SHARE', iconShare)

# Frame de pestañas

frameNoteTools = ttk.Notebook(tools, bootstyle='primary')
frameNoteTools.pack(padx=10, pady=2, fill=BOTH)

tabTools1 = ttk.Frame(frameNoteTools)
tabTools2 = ttk.Frame(frameNoteTools)
tabTools3 = ttk.Frame(frameNoteTools)
tabTools4 = ttk.Frame(frameNoteTools)

# Pestaña Seedtest

# Frame Cuadro destino

destinoFrameSpeedTest = Frame(tabTools3, width=80)
destinoFrameSpeedTest.pack(pady=2, padx=2)

ttk.Button(destinoFrameSpeedTest, text='TEST DE VELOCIDAD', style='custom.success.TButton',
           command=funcionSpeedTest).pack(padx=20, pady=10, side='right')

# Frame de respuesta

resultadoFrameSpeedTest = Frame(tabTools3, height=15, width=80)
resultadoFrameSpeedTest.pack(pady=2, padx=5)

# uploadMeter = ttk.Meter(resultadoFrameSpeedTest, metersize=150, amountused=25,
#                        bootstyle='success', subtext="Upload", interactive=True,
#                        textright="Mbps", stripethickness=1)
# uploadMeter.pack(side='left')

# downloadMeter = ttk.Meter(resultadoFrameSpeedTest, bootstyle='success',
#                          subtext="Download", interactive=True, textright="Mbps",
#                          metersize=500, stripethickness=1)

# downloadMeter.pack(side='left')

# Pestaña Wake on lan


# Frame Cuadro destino

destinoFrameWol = Frame(tabTools1, width=80)
destinoFrameWol.pack(pady=2, padx=2)


ttk.Button(destinoFrameWol, text='DESPERTAR', style='destino.success.TButton',
           command=funcionWol).pack(padx=20, pady=10, side='right')


textTargetWol = ttk.Entry(destinoFrameWol, width=30, font=("Courier", 15))
textTargetWol.pack(pady=10, side='right')


ttk.Label(destinoFrameWol, text='MAC DESTINO', style='destino.TLabel'
          ).pack(side='right')


# Frame de respuesta

resultadoFrameWol = Frame(tabTools1, height=15, width=80)
resultadoFrameWol.pack(pady=2, padx=5)


# Cuadro de texto resultado

resultadoWol = Text(resultadoFrameWol, height=15,
                    width=80, font=('Courier', 11))
resultadoWol.pack()


# Pestaña Temperatura

tempLabel = ttk.Label(tabTools2, text=' ', padding=10, font=('Helvetica', 18))
tempLabel.pack(pady=30)

humLabel = ttk.Label(tabTools2, text=' ', padding=10, font=('Helvetica', 18))
humLabel.pack(pady=10)

tomarTemperatura()

tempActualizar = ttk.Button(tabTools2, text='ACTUALIZAR', padding=4,
                            style='destino.success.TButton', command=tomarTemperatura)
tempActualizar.pack(padx=10, pady=10)

# Pestaña IP publica


def tomarIpPublica():

    comandoIpPublica = '/bin/curl ifconfig.me'
    p4 = subprocess.Popen(
        comandoIpPublica,
        stdout=subprocess.PIPE,
        universal_newlines=True,
        shell=True)

    ipResultado = f'La ip publica es {p4.stdout.readline()}'
    p4.terminate()
    ipPublica.config(text=ipResultado)


ipPublica = ttk.Label(tabTools4, text=' ', padding=10, font=('Helvetica', 18))
ipPublica.pack(pady=40)


ipActualizar = ttk.Button(
    tabTools4,
    text='ACTUALIZAR',
    padding=4,
    style='destino.success.TButton',
    command=tomarIpPublica)
ipActualizar.pack(padx=10, pady=10)

# Fin Pestañas

frameNoteTools.add(tabTools1, text='Wake on Lan')
frameNoteTools.add(tabTools2, text='Temperatura ambiente')
frameNoteTools.add(tabTools3, text='Test de velocidad')
frameNoteTools.add(tabTools4, text='Ip Publica')

##########################################  Fin Seccion Dump  ############

# Pagina principal

home.tkraise()
root.mainloop()
