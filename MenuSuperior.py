from tkinter import *
import ttkbootstrap as ttk
import subprocess

class MenuSuperior:
    # Iconos Barra Superior
    iconKeyboard = ''
    iconBack = ''
    
    contadorKeyboard = 0
    botonTeclado = ""

    def __init__(self, frame, texto,home):

        self.iconKeyboard = PhotoImage(file='./img/keyboard-2-32.png')
        self.iconBack = PhotoImage(file='./img/arrow-81-32.png')

        self.botonTeclado = ttk.Button(frame)

        ttk.Label(frame, text=texto,
            font=('Helvetica', 25)).pack(padx=5,pady=0, side='left')
                
        ttk.Button(frame, text='VOLVER', style='barraSuperior.primary.TButton',
                command=lambda: home.tkraise(), image=self.iconBack).pack(padx=5, pady=0, side='right')

        self.botonTeclado.configure(text='TECLADO', style='barraSuperior.primary.TButton', command=self.tecladoOnbord, image=self.iconKeyboard)
        self.botonTeclado.pack(padx=5, pady=0, side='right')

    def agregarBotonSuperior(self, frame, funcion, texto,img):

        ttk.Button(frame, text=texto, style='barraSuperior.primary.TButton',
                command=funcion, image=img).pack(padx=5, pady=0, side='right')        

    def tecladoOnbord(self):
           
        if self.contadorKeyboard % 2 == 0:
            subprocess.Popen('onboard')
            self.setColorVolver('danger')
            self.contadorKeyboard += 1

        else:
            subprocess.Popen('killall onboard',shell=True)
            self.setColorVolver('primary')
            self.contadorKeyboard += 1
    
    def setColorVolver(self,color):
        self.botonTeclado.configure(style=f'barraSuperior.{color}.TButton')