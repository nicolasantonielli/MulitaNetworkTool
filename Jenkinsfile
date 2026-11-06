// Pruebas estaticas y tests. Las reglas viven en pyproject.toml, asi corren igual en la PC y aqui.
// El agente necesita Python 3.10 o mas y PyQt5 del sistema (python3-pyqt5), como la Raspberry Pi.
pipeline {
  agent any
  options {
    timestamps()
    timeout(time: 20, unit: 'MINUTES')
  }
  environment {
    QT_QPA_PLATFORM = 'offscreen'
    MULITA_TEST = '1'
  }
  stages {
    stage('Preparar') {
      steps {
        sh 'python3 -m venv --system-site-packages .venv-ci'
        sh '.venv-ci/bin/pip install --quiet -r requirements-dev.txt'
      }
    }
    stage('Calidad') {
      steps {
        // Errores reales, trampas comunes y complejidad (umbral en pyproject.toml).
        sh '.venv-ci/bin/ruff check mulita tests'
        // Arquitectura en capas: core no importa nada, la interfaz no conoce adaptadores.
        sh '.venv-ci/bin/lint-imports'
      }
    }
    stage('Tipos (informativo)') {
      steps {
        // Hay errores de tipado heredados. No frena el build, lo deja inestable.
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          sh '.venv-ci/bin/mypy'
        }
      }
    }
    stage('Tests') {
      steps {
        sh 'mkdir -p reports'
        sh '.venv-ci/bin/pytest tests --junitxml=reports/junit.xml'
      }
    }
  }
  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
    }
  }
}
