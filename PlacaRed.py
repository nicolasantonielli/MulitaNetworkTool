import subprocess
import json


class PlacaRed:

    interfacesEth = []
    interfacesIP = []
    interfacesMac = []

    def tomarInterface(self):

        self.interfacesEth.clear()
        comando = '/usr/bin/ip -j link'
        pro1 = subprocess.Popen(
            comando, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        resultado = pro1.stdout.read()
        resultadoJson = json.loads(resultado)
        for i in range(len(resultadoJson)):
            self.interfacesEth.append(resultadoJson[i]["ifname"])

        return self.interfacesEth

    def tomarIps(self):
        self.interfacesIP.clear()

        comandoip = '/usr/bin/ip -j add'
        pro2 = subprocess.Popen(
            comandoip, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        resultado = pro2.stdout.read()
        resultadoJson = json.loads(resultado)

        for i in range(len(resultadoJson)):
            self.interfacesIP.append(resultadoJson[i]['addr_info'][0]['local'])

        return self.interfacesIP

    def tomarMac(self):
        self.interfacesMac.clear()

        comandoip = '/usr/bin/ip -j add'
        pro3 = subprocess.Popen(
            comandoip, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        resultado = pro3.stdout.read()
        resultadoJson = json.loads(resultado)

        for i in range(len(resultadoJson)):
            self.interfacesMac.append(resultadoJson[i]['address'])
        print(self.interfacesMac)
        return self.interfacesMac
