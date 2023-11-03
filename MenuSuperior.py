from tkinter import *
import ttkbootstrap as ttk
import subprocess

class MenuSuperior:
    # Iconos Barra Superior
    #iconKeyboard = PhotoImage(file='./img/keyboard-2-32.png')
    #iconBack = PhotoImage(file='./img/arrow-81-32.png')
    
    contadorKeyboard = 0

    botonVolver=ttk.Button()
    botonTeclado=ttk.Button()

    def __init__(self, frame, texto,home):

#        self.iconKeyboard = PhotoImage(file='./img/keyboard-2-32.png')
#        self.iconBack = PhotoImage(file='./img/arrow-81-32.png')

        ttk.Label(frame, text=texto,
            font=('Helvetica', 25)).pack(padx=5,pady=0, side='left')
        
        self.botonVolver = self.agregarBotonSuperiorRetorno(frame, home.tkraise(), 'VOLVER')#, self.iconBack)
        self.botonVolver.pack(padx=5, pady=0, side='right')

        self.botonTeclado = self.agregarBotonSuperiorRetorno(frame, self.tecladoOnbord, 'TECLADO')#, self.iconKeyboard)
        self.botonVolver.pack(padx=5, pady=0, side='right')

    def agregarBotonSuperiorRetorno(self, frame, funcion, texto):

       boton = ttk.Button(frame, text=texto, style='barraSuperior.primary.TButton',
                command=funcion)

       return boton
    
    def agregarBotonSuperior(self, frame, funcion, texto):

        ttk.Button(frame, text=texto, style='barraSuperior.primary.TButton',
            command=funcion).pack(padx=5, pady=0, side='right')

    
    def tecladoOnbord(self):
           
        if self.contadorKeyboard % 2 == 0:
            subprocess.Popen('onboard')
            self.setColorVolver('danger', self.botonTeclado)
            self.contadorKeyboard += 1

        else:
            subprocess.Popen('killall onboard',shell=True)
            self.setColorVolver('primary', self.botonTeclado)
            self.contadorKeyboard += 1
    
    def setColorVolver(self,color, boton):
        boton.configure(style=f'barraSuperior.{color}.TButton')