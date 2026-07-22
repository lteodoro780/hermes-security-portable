#!/usr/bin/env python3
"""Interface desktop nativa do HERMES Security Portable 0.9.0.

O executável desta versão não inicia servidor HTTP e não abre navegador. A
janela Qt chama diretamente os mesmos módulos locais já usados e testados nas
versões anteriores.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

try:
    from . import hermes_backup, hermes_incidents, hermes_knowledge, hermes_models, hermes_monitor, hermes_web
    from .hermes_desktop_core import (
        APP_VERSION,
        DesktopError,
        ModelRuntimeController,
        complete_setup,
        format_bytes,
        port_is_open,
        register_custom_model,
        register_llama_executable,
        startup_payload,
    )
    from .hermes_history import append_chat_exchange, clear_chat_history, load_chat_history
    from .hermes_paths import APP_DIR, MODELS_DIR, REPORT_DIR, ensure_runtime_directories, runtime_path_payload
    from .hermes_profiles import (
        ALLOWED_CONTEXT_SIZES,
        PROFILE_DEFINITIONS,
        PROFILE_ORDER,
        hardware_info,
        load_config,
        profile_catalog,
        runtime_selection,
        save_config,
    )
except ImportError:  # PyInstaller executa o arquivo como módulo de topo.
    import hermes_backup
    import hermes_incidents
    import hermes_knowledge
    import hermes_models
    import hermes_monitor
    import hermes_web
    from hermes_desktop_core import (
        APP_VERSION,
        DesktopError,
        ModelRuntimeController,
        complete_setup,
        format_bytes,
        port_is_open,
        register_custom_model,
        register_llama_executable,
        startup_payload,
    )
    from hermes_history import append_chat_exchange, clear_chat_history, load_chat_history
    from hermes_paths import APP_DIR, MODELS_DIR, REPORT_DIR, ensure_runtime_directories, runtime_path_payload
    from hermes_profiles import (
        ALLOWED_CONTEXT_SIZES,
        PROFILE_DEFINITIONS,
        PROFILE_ORDER,
        hardware_info,
        load_config,
        profile_catalog,
        runtime_selection,
        save_config,
    )


APP_NAME = "HERMES Security Portable"
NAV_ITEMS = (
    "Visão geral",
    "Diagnósticos",
    "Monitor",
    "Incidentes",
    "Assistente IA",
    "Base Local",
    "Modelos",
    "Backup",
    "Configurações",
)
SEVERITY_LABELS = {"normal": "Normal", "attention": "Atenção", "critical": "Crítico"}
STATUS_LABELS = {"open": "Em aberto", "investigating": "Investigando", "resolved": "Resolvido"}
STATE_LABELS = {
    "running": "IA ativa",
    "external": "IA externa detectada",
    "starting": "IA iniciando",
    "model_missing": "Modelo não configurado",
    "engine_missing": "llama.cpp não configurado",
    "stopped": "IA parada",
}


STYLE_SHEET = """
QWidget { background: #07111f; color: #e8f2ff; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QDialog, QWizard { background: #07111f; }
QFrame#sidebar { background: #091726; border-right: 1px solid #1f3851; }
QFrame#topbar { background: #0a1929; border-bottom: 1px solid #1f3851; }
QFrame[card="true"], QGroupBox { background: #0d1d2f; border: 1px solid #203a53; border-radius: 10px; }
QGroupBox { margin-top: 11px; padding: 17px 12px 12px; font-weight: 600; color: #a9bdd1; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLabel#brand { color: #4ed9ff; font-size: 21px; font-weight: 800; letter-spacing: 1px; }
QLabel#subtitle, QLabel[muted="true"] { color: #8fa6bd; }
QLabel[metric="true"] { font-size: 28px; font-weight: 700; color: #f4f9ff; }
QLabel[accent="true"] { color: #4ed9ff; font-weight: 600; }
QListWidget#navigation { background: transparent; border: 0; outline: 0; padding: 6px; }
QListWidget#navigation::item { padding: 12px 14px; margin: 2px 0; border-radius: 7px; color: #aebfd0; }
QListWidget#navigation::item:hover { background: #11283e; color: #edf8ff; }
QListWidget#navigation::item:selected { background: #153650; color: #5ee0ff; border-left: 3px solid #48d7ff; }
QPushButton { background: #153650; border: 1px solid #28516d; border-radius: 7px; padding: 8px 13px; color: #ecf7ff; font-weight: 600; }
QPushButton:hover { background: #1a4665; border-color: #41c8ed; }
QPushButton:pressed { background: #0e2b42; }
QPushButton:disabled { background: #132333; color: #62788c; border-color: #203346; }
QPushButton[primary="true"] { background: #0f7897; border-color: #36c7e9; color: white; }
QPushButton[danger="true"] { background: #5b2530; border-color: #9b4356; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox, QTableWidget, QListWidget:not(#navigation) {
  background: #081521; border: 1px solid #29445d; border-radius: 6px; padding: 6px; selection-background-color: #17637f;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #45d0f2; }
QComboBox::drop-down { border: 0; width: 24px; }
QTableWidget { gridline-color: #1d3449; alternate-background-color: #0b1a29; }
QHeaderView::section { background: #10263a; color: #91b0ca; padding: 7px; border: 0; border-right: 1px solid #20394e; }
QProgressBar { background: #0a1825; border: 1px solid #29445d; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: #24a9ca; border-radius: 4px; }
QScrollBar:vertical { width: 10px; background: #081521; }
QScrollBar::handle:vertical { background: #29465e; min-height: 24px; border-radius: 5px; }
QStatusBar { background: #091726; color: #8fa6bd; border-top: 1px solid #1f3851; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QToolTip { background: #10263a; color: #f4f9ff; border: 1px solid #3b627f; }
"""


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:  # A mensagem é apresentada sem derrubar a janela.
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


def horizontal_line() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color:#1f3851")
    return line


def card(title: str, value: str = "—") -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setProperty("card", True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 13, 16, 13)
    heading = QLabel(title.upper())
    heading.setProperty("muted", True)
    metric = QLabel(value)
    metric.setProperty("metric", True)
    layout.addWidget(heading)
    layout.addWidget(metric)
    return frame, metric


def table_item(value: Any, data: Any = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(value if value is not None else "—"))
    if data is not None:
        item.setData(Qt.ItemDataRole.UserRole, data)
    return item


def configure_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)


class FirstRunWizard(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuração inicial — HERMES 0.9.0")
        self.setMinimumSize(720, 500)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self._model_label = QLabel("Nenhum modelo selecionado. O HERMES pode funcionar sem IA.")
        self._model_label.setWordWrap(True)
        self._llama_label = QLabel("llama.cpp ainda não localizado.")
        self._llama_label.setWordWrap(True)
        self._build_pages()

    def _build_pages(self) -> None:
        welcome = QWizardPage()
        welcome.setTitle("Bem-vindo ao HERMES Desktop")
        welcome.setSubTitle("A versão 0.9.0 funciona como programa nativo e não abre navegador.")
        layout = QVBoxLayout(welcome)
        text = QLabel(
            "O monitor, os diagnósticos, os incidentes, os relatórios e o backup "
            "funcionam mesmo sem um modelo. Você pode adicionar a IA agora ou depois."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch()
        self.addPage(welcome)

        hardware_page = QWizardPage()
        hardware_page.setTitle("Perfil recomendado")
        hardware = hardware_info()
        runtime = runtime_selection()
        hardware_page.setSubTitle("A recomendação é calculada localmente, sem enviar dados.")
        form = QFormLayout(hardware_page)
        form.addRow("Processador", QLabel(str(hardware.get("cpu_name", "—"))))
        form.addRow("Memória", QLabel(f"{hardware.get('memory_total_gb', '—')} GB"))
        form.addRow(
            "Núcleos",
            QLabel(f"{hardware.get('physical_cores', '—')} físicos / {hardware.get('logical_cores', '—')} threads"),
        )
        form.addRow("Perfil", QLabel(str(runtime["profile"].get("label", "Automático"))))
        self.addPage(hardware_page)

        model_page = QWizardPage()
        model_page.setTitle("Modelo de IA opcional")
        model_page.setSubTitle("Escolha qualquer modelo GGUF compatível com llama.cpp.")
        model_layout = QVBoxLayout(model_page)
        self._model_label.setProperty("muted", True)
        model_layout.addWidget(self._model_label)
        select_model = QPushButton("Selecionar modelo .gguf")
        select_model.setProperty("primary", True)
        select_model.clicked.connect(self._select_model)
        model_layout.addWidget(select_model)
        model_layout.addWidget(horizontal_line())
        self._llama_label.setProperty("muted", True)
        model_layout.addWidget(self._llama_label)
        select_llama = QPushButton("Localizar llama-server.exe")
        select_llama.clicked.connect(self._select_llama)
        model_layout.addWidget(select_llama)
        note = QLabel("Você também pode concluir agora e configurar tudo na tela Modelos.")
        note.setProperty("muted", True)
        note.setWordWrap(True)
        model_layout.addWidget(note)
        model_layout.addStretch()
        self.addPage(model_page)

        finish = QWizardPage()
        finish.setTitle("Configuração concluída")
        finish.setSubTitle("O HERMES abrirá a janela principal.")
        finish_layout = QVBoxLayout(finish)
        finish_layout.addWidget(
            QLabel("Se nenhum modelo foi selecionado, todos os recursos defensivos continuam disponíveis.")
        )
        finish_layout.addStretch()
        self.addPage(finish)

    def _select_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar modelo GGUF", str(MODELS_DIR), "Modelos GGUF (*.gguf)")
        if not path:
            return
        try:
            result = register_custom_model(path)
        except Exception as exc:
            QMessageBox.warning(self, "Modelo inválido", str(exc))
            return
        self._model_label.setText(f"Selecionado: {result['name']} • {result['size_label']}")

    def _select_llama(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Localizar llama.cpp",
            str(APP_DIR),
            "llama.cpp (llama-server.exe llama.exe);;Executáveis (*.exe);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            result = register_llama_executable(path)
        except Exception as exc:
            QMessageBox.warning(self, "Executável inválido", str(exc))
            return
        self._llama_label.setText(f"Motor selecionado: {result['name']}")

    def accept(self) -> None:
        complete_setup()
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self, *, smoke_mode: bool = False) -> None:
        super().__init__()
        self.smoke_mode = smoke_mode
        self.runtime_controller = ModelRuntimeController()
        self.monitor_engine = hermes_monitor.MonitoringEngine()
        self.thread_pool = QThreadPool.globalInstance()
        self._active_tasks = 0
        self._incident_syncing = False
        self._current_incident_id: str | None = None
        self._current_report: str | None = None
        self._last_download_status: str | None = None
        self._knowledge_last: dict[str, Any] | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(1040, 680)
        self.setStyleSheet(STYLE_SHEET)
        self._build_shell()
        self._build_pages()
        self._configure_timers()
        if not smoke_mode:
            try:
                self.monitor_engine.start_if_enabled()
            except Exception:
                pass
        self.refresh_all()

    def _build_shell(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        brand = QLabel("HERMES")
        brand.setObjectName("brand")
        version = QLabel(f"SECURITY DESKTOP  •  {APP_VERSION}")
        version.setObjectName("subtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(version)
        sidebar_layout.addSpacing(20)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        for label in NAV_ITEMS:
            self.navigation.addItem(label)
        sidebar_layout.addWidget(self.navigation, 1)
        self.sidebar_state = QLabel("Núcleo local")
        self.sidebar_state.setProperty("accent", True)
        sidebar_layout.addWidget(self.sidebar_state)
        self.sidebar_detail = QLabel("Inicializando…")
        self.sidebar_detail.setProperty("muted", True)
        self.sidebar_detail.setWordWrap(True)
        sidebar_layout.addWidget(self.sidebar_detail)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("topbar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(24, 13, 24, 13)
        self.page_title = QLabel(NAV_ITEMS[0])
        self.page_title.setStyleSheet("font-size:18px;font-weight:700")
        self.desktop_badge = QLabel("● DESKTOP NATIVO")
        self.desktop_badge.setProperty("accent", True)
        top_layout.addWidget(self.page_title)
        top_layout.addStretch()
        top_layout.addWidget(self.desktop_badge)
        content_layout.addWidget(topbar)

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_message = QLabel("Pronto")
        self.task_progress = QProgressBar()
        self.task_progress.setFixedWidth(180)
        self.task_progress.setRange(0, 0)
        self.task_progress.hide()
        status.addWidget(self.status_message, 1)
        status.addPermanentWidget(self.task_progress)

        self.navigation.currentRowChanged.connect(self._change_page)
        self.navigation.setCurrentRow(0)

    def _build_pages(self) -> None:
        self.pages.addWidget(self._overview_page())
        self.pages.addWidget(self._diagnostics_page())
        self.pages.addWidget(self._monitor_page())
        self.pages.addWidget(self._incidents_page())
        self.pages.addWidget(self._assistant_page())
        self.pages.addWidget(self._knowledge_page())
        self.pages.addWidget(self._models_page())
        self.pages.addWidget(self._backup_page())
        self.pages.addWidget(self._settings_page())

    def _page_container(self) -> tuple[QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 22, 24, 28)
        layout.setSpacing(14)
        scroll.setWidget(body)
        return scroll, layout

    def _overview_page(self) -> QWidget:
        page, layout = self._page_container()
        intro = QLabel("Estado do computador e dos serviços locais")
        intro.setProperty("muted", True)
        layout.addWidget(intro)
        grid = QGridLayout()
        self.metric_labels: dict[str, QLabel] = {}
        for index, (key, title) in enumerate(
            (("cpu", "CPU"), ("memory", "Memória"), ("disk", "Disco"), ("network", "Rede"))
        ):
            widget, label = card(title)
            self.metric_labels[key] = label
            grid.addWidget(widget, 0, index)
        layout.addLayout(grid)

        status_grid = QGridLayout()
        model_box = QGroupBox("Assistente local")
        model_layout = QVBoxLayout(model_box)
        self.overview_model = QLabel("Verificando modelo…")
        self.overview_model.setStyleSheet("font-size:17px;font-weight:700")
        self.overview_engine = QLabel("—")
        self.overview_engine.setProperty("muted", True)
        model_buttons = QHBoxLayout()
        start_ai = QPushButton("Iniciar IA")
        start_ai.setProperty("primary", True)
        start_ai.clicked.connect(self.start_ai)
        models = QPushButton("Gerenciar modelos")
        models.clicked.connect(lambda: self.navigation.setCurrentRow(6))
        model_buttons.addWidget(start_ai)
        model_buttons.addWidget(models)
        model_layout.addWidget(self.overview_model)
        model_layout.addWidget(self.overview_engine)
        model_layout.addLayout(model_buttons)
        status_grid.addWidget(model_box, 0, 0)

        monitor_box = QGroupBox("Monitoramento contínuo")
        monitor_layout = QVBoxLayout(monitor_box)
        self.overview_monitor = QLabel("Monitor parado")
        self.overview_monitor.setStyleSheet("font-size:17px;font-weight:700")
        self.overview_alerts = QLabel("—")
        self.overview_alerts.setProperty("muted", True)
        monitor_buttons = QHBoxLayout()
        monitor_start = QPushButton("Ativar monitor")
        monitor_start.setProperty("primary", True)
        monitor_start.clicked.connect(self.start_monitor)
        monitor_open = QPushButton("Abrir monitor")
        monitor_open.clicked.connect(lambda: self.navigation.setCurrentRow(2))
        monitor_buttons.addWidget(monitor_start)
        monitor_buttons.addWidget(monitor_open)
        monitor_layout.addWidget(self.overview_monitor)
        monitor_layout.addWidget(self.overview_alerts)
        monitor_layout.addLayout(monitor_buttons)
        status_grid.addWidget(monitor_box, 0, 1)
        layout.addLayout(status_grid)

        quick = QGroupBox("Ações rápidas")
        quick_layout = QHBoxLayout(quick)
        for text, diagnostic in (
            ("Diagnóstico do sistema", "system"),
            ("Diagnóstico de rede", "network"),
            ("Diagnóstico completo", "full"),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, kind=diagnostic: self.run_diagnostic(kind))
            quick_layout.addWidget(button)
        incident = QPushButton("Novo incidente")
        incident.clicked.connect(self.new_incident)
        quick_layout.addWidget(incident)
        layout.addWidget(quick)
        layout.addStretch()
        return page

    def _diagnostics_page(self) -> QWidget:
        page, layout = self._page_container()
        buttons = QHBoxLayout()
        for text, diagnostic in (
            ("Sistema", "system"),
            ("Rede", "network"),
            ("Completo", "full"),
        ):
            button = QPushButton(f"Executar: {text}")
            if diagnostic == "full":
                button.setProperty("primary", True)
            button.clicked.connect(lambda _checked=False, kind=diagnostic: self.run_diagnostic(kind))
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Orientation.Vertical)
        reports_box = QGroupBox("Relatórios locais")
        reports_layout = QVBoxLayout(reports_box)
        self.reports_table = QTableWidget(0, 5)
        self.reports_table.setHorizontalHeaderLabels(("Data", "Tipo", "Verificações", "Alertas", "Arquivo"))
        configure_table(self.reports_table)
        self.reports_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.reports_table.itemSelectionChanged.connect(self.show_selected_report)
        reports_layout.addWidget(self.reports_table)
        export_row = QHBoxLayout()
        export_html = QPushButton("Exportar HTML")
        export_html.clicked.connect(self.export_report_html)
        refresh = QPushButton("Atualizar lista")
        refresh.clicked.connect(self.refresh_reports)
        export_row.addWidget(export_html)
        export_row.addWidget(refresh)
        export_row.addStretch()
        reports_layout.addLayout(export_row)
        splitter.addWidget(reports_box)

        result_box = QGroupBox("Resultado selecionado")
        result_layout = QVBoxLayout(result_box)
        self.diagnostic_result = QPlainTextEdit()
        self.diagnostic_result.setReadOnly(True)
        self.diagnostic_result.setPlaceholderText("Execute ou selecione um diagnóstico para ver os detalhes.")
        result_layout.addWidget(self.diagnostic_result)
        splitter.addWidget(result_box)
        splitter.setSizes((320, 300))
        layout.addWidget(splitter, 1)
        return page

    def _monitor_page(self) -> QWidget:
        page, layout = self._page_container()
        top = QHBoxLayout()
        self.monitor_state = QLabel("Monitor parado")
        self.monitor_state.setStyleSheet("font-size:17px;font-weight:700")
        start = QPushButton("Ativar")
        start.setProperty("primary", True)
        start.clicked.connect(self.start_monitor)
        stop = QPushButton("Parar")
        stop.clicked.connect(self.stop_monitor)
        top.addWidget(self.monitor_state)
        top.addStretch()
        top.addWidget(start)
        top.addWidget(stop)
        layout.addLayout(top)

        config_box = QGroupBox("Limites e coleta")
        config_grid = QGridLayout(config_box)
        self.monitor_interval = QComboBox()
        for value in sorted(hermes_monitor.ALLOWED_INTERVALS):
            self.monitor_interval.addItem(f"{value} segundos", value)
        config_grid.addWidget(QLabel("Intervalo"), 0, 0)
        config_grid.addWidget(self.monitor_interval, 0, 1)
        self.monitor_thresholds: dict[str, tuple[QSpinBox, QSpinBox]] = {}
        for row, (resource, label) in enumerate((("cpu", "CPU"), ("memory", "Memória"), ("disk", "Disco")), start=1):
            warning = QSpinBox()
            warning.setRange(50, 98)
            warning.setSuffix(" %")
            critical = QSpinBox()
            critical.setRange(55, 100)
            critical.setSuffix(" %")
            self.monitor_thresholds[resource] = (warning, critical)
            config_grid.addWidget(QLabel(label), row, 0)
            config_grid.addWidget(warning, row, 1)
            config_grid.addWidget(QLabel("Crítico"), row, 2)
            config_grid.addWidget(critical, row, 3)
        save = QPushButton("Salvar limites")
        save.clicked.connect(self.save_monitor_settings)
        config_grid.addWidget(save, 0, 3)
        layout.addWidget(config_box)

        alerts_box = QGroupBox("Alertas recentes")
        alerts_layout = QVBoxLayout(alerts_box)
        self.alerts_table = QTableWidget(0, 6)
        self.alerts_table.setHorizontalHeaderLabels(("Data", "Recurso", "Nível", "Valor", "Estado", "Mensagem"))
        configure_table(self.alerts_table)
        self.alerts_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        alerts_layout.addWidget(self.alerts_table)
        actions = QHBoxLayout()
        acknowledge = QPushButton("Marcar como visto")
        acknowledge.clicked.connect(self.acknowledge_alert)
        open_incident = QPushButton("Abrir incidente")
        open_incident.setProperty("primary", True)
        open_incident.clicked.connect(self.incident_from_alert)
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self.refresh_monitor)
        actions.addWidget(acknowledge)
        actions.addWidget(open_incident)
        actions.addWidget(refresh)
        actions.addStretch()
        alerts_layout.addLayout(actions)
        layout.addWidget(alerts_box, 1)
        return page

    def _incidents_page(self) -> QWidget:
        page, layout = self._page_container()
        top = QHBoxLayout()
        self.incident_summary_label = QLabel("Nenhum incidente")
        self.incident_summary_label.setProperty("muted", True)
        new_button = QPushButton("Novo incidente")
        new_button.setProperty("primary", True)
        new_button.clicked.connect(self.new_incident)
        top.addWidget(self.incident_summary_label)
        top.addStretch()
        top.addWidget(new_button)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        list_box = QGroupBox("Central de incidentes")
        list_layout = QVBoxLayout(list_box)
        self.incidents_table = QTableWidget(0, 4)
        self.incidents_table.setHorizontalHeaderLabels(("Estado", "Severidade", "Título", "Atualizado"))
        configure_table(self.incidents_table)
        self.incidents_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.incidents_table.itemSelectionChanged.connect(self.show_selected_incident)
        list_layout.addWidget(self.incidents_table)
        splitter.addWidget(list_box)

        detail_box = QGroupBox("Detalhes")
        detail_layout = QVBoxLayout(detail_box)
        self.incident_title = QLabel("Selecione um incidente")
        self.incident_title.setStyleSheet("font-size:18px;font-weight:700")
        self.incident_meta = QLabel("—")
        self.incident_meta.setProperty("muted", True)
        status_row = QHBoxLayout()
        self.incident_status = QComboBox()
        for value, label in STATUS_LABELS.items():
            self.incident_status.addItem(label, value)
        self.incident_status.currentIndexChanged.connect(self.change_incident_status)
        note = QPushButton("Adicionar nota")
        note.clicked.connect(self.add_incident_note)
        analyse = QPushButton("Analisar com IA")
        analyse.clicked.connect(self.analyse_incident)
        status_row.addWidget(QLabel("Estado"))
        status_row.addWidget(self.incident_status)
        status_row.addWidget(note)
        status_row.addWidget(analyse)
        self.incident_checklist = QListWidget()
        self.incident_checklist.itemChanged.connect(self.toggle_checklist_item)
        self.incident_timeline = QPlainTextEdit()
        self.incident_timeline.setReadOnly(True)
        export_row = QHBoxLayout()
        export_html = QPushButton("Exportar HTML")
        export_html.clicked.connect(lambda: self.export_incident("html"))
        export_pdf = QPushButton("Exportar PDF")
        export_pdf.clicked.connect(lambda: self.export_incident("pdf"))
        export_row.addWidget(export_html)
        export_row.addWidget(export_pdf)
        export_row.addStretch()
        detail_layout.addWidget(self.incident_title)
        detail_layout.addWidget(self.incident_meta)
        detail_layout.addLayout(status_row)
        detail_layout.addWidget(QLabel("Checklist defensivo"))
        detail_layout.addWidget(self.incident_checklist)
        detail_layout.addWidget(QLabel("Linha do tempo"))
        detail_layout.addWidget(self.incident_timeline)
        detail_layout.addLayout(export_row)
        splitter.addWidget(detail_box)
        splitter.setSizes((520, 650))
        layout.addWidget(splitter, 1)
        return page

    def _assistant_page(self) -> QWidget:
        page, layout = self._page_container()
        top = QHBoxLayout()
        self.assistant_state = QLabel("IA não iniciada")
        self.assistant_state.setStyleSheet("font-size:17px;font-weight:700")
        self.assistant_mode = QComboBox()
        self.assistant_mode.addItem("Resposta rápida", "quick")
        self.assistant_mode.addItem("Análise profunda", "deep")
        start = QPushButton("Iniciar IA")
        start.clicked.connect(self.start_ai)
        models = QPushButton("Modelos")
        models.clicked.connect(lambda: self.navigation.setCurrentRow(6))
        top.addWidget(self.assistant_state)
        top.addStretch()
        top.addWidget(self.assistant_mode)
        top.addWidget(start)
        top.addWidget(models)
        layout.addLayout(top)

        self.chat_history = QTextBrowser()
        self.chat_history.setOpenExternalLinks(False)
        layout.addWidget(self.chat_history, 1)
        self.chat_input = QPlainTextEdit()
        self.chat_input.setPlaceholderText("Digite uma pergunta sobre suporte, diagnóstico ou segurança defensiva…")
        self.chat_input.setMaximumHeight(120)
        layout.addWidget(self.chat_input)
        actions = QHBoxLayout()
        clear = QPushButton("Limpar histórico")
        clear.clicked.connect(self.clear_chat)
        send = QPushButton("Enviar")
        send.setProperty("primary", True)
        send.clicked.connect(self.send_chat)
        actions.addWidget(clear)
        actions.addStretch()
        actions.addWidget(send)
        layout.addLayout(actions)
        return page

    def _models_page(self) -> QWidget:
        page, layout = self._page_container()
        state_box = QGroupBox("Modelo ativo")
        state_layout = QVBoxLayout(state_box)
        self.model_name = QLabel("Nenhum modelo configurado")
        self.model_name.setStyleSheet("font-size:20px;font-weight:700")
        self.model_path = QLabel("—")
        self.model_path.setWordWrap(True)
        self.model_path.setProperty("muted", True)
        self.model_engine = QLabel("llama.cpp: não configurado")
        self.model_engine.setProperty("muted", True)
        state_layout.addWidget(self.model_name)
        state_layout.addWidget(self.model_path)
        state_layout.addWidget(self.model_engine)
        runtime_buttons = QHBoxLayout()
        start = QPushButton("Iniciar IA")
        start.setProperty("primary", True)
        start.clicked.connect(self.start_ai)
        stop = QPushButton("Parar IA")
        stop.clicked.connect(self.stop_ai)
        logs = QPushButton("Abrir pasta de logs")
        logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR / "logs"))))
        runtime_buttons.addWidget(start)
        runtime_buttons.addWidget(stop)
        runtime_buttons.addWidget(logs)
        runtime_buttons.addStretch()
        state_layout.addLayout(runtime_buttons)
        layout.addWidget(state_box)

        import_box = QGroupBox("Adicionar modelo GGUF")
        import_layout = QVBoxLayout(import_box)
        note = QLabel(
            "Use o modelo no local atual ou copie-o para a pasta portátil. "
            "O arquivo é validado antes de ser ativado."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        self.copy_model_checkbox = QCheckBox("Copiar o arquivo para a pasta models do HERMES")
        import_buttons = QHBoxLayout()
        choose_model = QPushButton("Selecionar arquivo .gguf")
        choose_model.setProperty("primary", True)
        choose_model.clicked.connect(self.choose_custom_model)
        choose_llama = QPushButton("Localizar llama-server.exe")
        choose_llama.clicked.connect(self.choose_llama)
        open_models = QPushButton("Abrir pasta models")
        open_models.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(MODELS_DIR))))
        import_buttons.addWidget(choose_model)
        import_buttons.addWidget(choose_llama)
        import_buttons.addWidget(open_models)
        import_buttons.addStretch()
        import_layout.addWidget(note)
        import_layout.addWidget(self.copy_model_checkbox)
        import_layout.addLayout(import_buttons)
        layout.addWidget(import_box)

        download_box = QGroupBox("Modelos oficiais sugeridos")
        download_layout = QVBoxLayout(download_box)
        self.preset_combo = QComboBox()
        for profile_id in PROFILE_ORDER:
            definition = PROFILE_DEFINITIONS[profile_id]
            self.preset_combo.addItem(
                f"{definition['label']} — {definition['model']} — {definition['approx_size']}",
                profile_id,
            )
        download_actions = QHBoxLayout()
        download = QPushButton("Baixar / continuar")
        download.setProperty("primary", True)
        download.clicked.connect(self.start_model_download)
        cancel = QPushButton("Pausar")
        cancel.clicked.connect(self.cancel_model_download)
        download_actions.addWidget(self.preset_combo, 1)
        download_actions.addWidget(download)
        download_actions.addWidget(cancel)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 1000)
        self.download_progress.setValue(0)
        self.download_state = QLabel("Nenhum download em andamento.")
        self.download_state.setProperty("muted", True)
        download_layout.addLayout(download_actions)
        download_layout.addWidget(self.download_progress)
        download_layout.addWidget(self.download_state)
        layout.addWidget(download_box)
        layout.addStretch()
        return page

    def _knowledge_page(self) -> QWidget:
        page, layout = self._page_container()
        top = QHBoxLayout()
        self.knowledge_collection = QComboBox()
        create_collection = QPushButton("Nova coleção")
        create_collection.clicked.connect(self.create_knowledge_collection)
        import_document = QPushButton("Importar documento")
        import_document.setProperty("primary", True)
        import_document.clicked.connect(self.import_knowledge_document)
        top.addWidget(QLabel("Coleção"))
        top.addWidget(self.knowledge_collection, 1)
        top.addWidget(create_collection)
        top.addWidget(import_document)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Vertical)
        documents_box = QGroupBox("Documentos indexados localmente")
        documents_layout = QVBoxLayout(documents_box)
        self.knowledge_documents = QTableWidget(0, 4)
        self.knowledge_documents.setHorizontalHeaderLabels(("Título", "Coleção", "Tamanho", "Importado"))
        configure_table(self.knowledge_documents)
        self.knowledge_documents.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        documents_layout.addWidget(self.knowledge_documents)
        document_actions = QHBoxLayout()
        delete_document = QPushButton("Excluir selecionado")
        delete_document.setProperty("danger", True)
        delete_document.clicked.connect(self.delete_knowledge_document)
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self.refresh_knowledge)
        document_actions.addWidget(delete_document)
        document_actions.addWidget(refresh)
        document_actions.addStretch()
        documents_layout.addLayout(document_actions)
        splitter.addWidget(documents_box)

        search_box = QGroupBox("Pesquisar e perguntar")
        search_layout = QVBoxLayout(search_box)
        search_row = QHBoxLayout()
        self.knowledge_query = QLineEdit()
        self.knowledge_query.setPlaceholderText("Ex.: como verificar DNS no ambiente?")
        self.knowledge_query.returnPressed.connect(self.search_knowledge)
        search_button = QPushButton("Pesquisar")
        search_button.clicked.connect(self.search_knowledge)
        ask_button = QPushButton("Perguntar à IA com fontes")
        ask_button.setProperty("primary", True)
        ask_button.clicked.connect(self.ask_knowledge)
        search_row.addWidget(self.knowledge_query, 1)
        search_row.addWidget(search_button)
        search_row.addWidget(ask_button)
        self.knowledge_results = QPlainTextEdit()
        self.knowledge_results.setReadOnly(True)
        self.knowledge_results.setPlaceholderText("A pesquisa funciona offline, mesmo sem modelo de IA.")
        search_layout.addLayout(search_row)
        search_layout.addWidget(self.knowledge_results)
        splitter.addWidget(search_box)
        splitter.setSizes((300, 300))
        layout.addWidget(splitter, 1)
        return page

    def _backup_page(self) -> QWidget:
        page, layout = self._page_container()
        info = QLabel(
            "O backup inclui configurações, históricos, incidentes, Base Local e relatórios. "
            "Modelos e executáveis não são incluídos."
        )
        info.setWordWrap(True)
        info.setProperty("muted", True)
        layout.addWidget(info)
        actions_box = QGroupBox("Backup portátil")
        actions = QHBoxLayout(actions_box)
        create = QPushButton("Exportar backup ZIP")
        create.setProperty("primary", True)
        create.clicked.connect(self.create_backup)
        restore = QPushButton("Restaurar backup")
        restore.clicked.connect(self.restore_backup)
        actions.addWidget(create)
        actions.addWidget(restore)
        actions.addStretch()
        layout.addWidget(actions_box)
        self.backup_result = QPlainTextEdit()
        self.backup_result.setReadOnly(True)
        self.backup_result.setPlaceholderText("O resultado da operação aparecerá aqui.")
        layout.addWidget(self.backup_result, 1)
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page_container()
        hardware_box = QGroupBox("Hardware detectado")
        hardware_form = QFormLayout(hardware_box)
        hardware = hardware_info()
        hardware_form.addRow("CPU", QLabel(str(hardware.get("cpu_name", "—"))))
        hardware_form.addRow("Memória", QLabel(f"{hardware.get('memory_total_gb', '—')} GB"))
        hardware_form.addRow("Vídeo", QLabel(str(hardware.get("graphics_name", "—"))))
        layout.addWidget(hardware_box)

        settings_box = QGroupBox("Desempenho da IA")
        form = QFormLayout(settings_box)
        self.settings_profile = QComboBox()
        self.settings_profile.addItem("Automático", "auto")
        for profile_id in PROFILE_ORDER:
            self.settings_profile.addItem(PROFILE_DEFINITIONS[profile_id]["label"], profile_id)
        self.settings_profile.addItem("Modelo personalizado", "custom")
        self.settings_mode = QComboBox()
        self.settings_mode.addItem("Resposta rápida", "quick")
        self.settings_mode.addItem("Análise profunda", "deep")
        self.settings_context = QComboBox()
        for size in ALLOWED_CONTEXT_SIZES:
            self.settings_context.addItem(f"{size} tokens", size)
        self.settings_threads = QSpinBox()
        self.settings_threads.setRange(0, 128)
        self.settings_threads.setSpecialValueText("Automático")
        self.settings_gpu = QSpinBox()
        self.settings_gpu.setRange(0, 999)
        self.settings_gpu.setSpecialValueText("Somente CPU")
        form.addRow("Perfil", self.settings_profile)
        form.addRow("Modo padrão", self.settings_mode)
        form.addRow("Contexto", self.settings_context)
        form.addRow("Threads", self.settings_threads)
        form.addRow("Camadas na GPU", self.settings_gpu)
        save = QPushButton("Salvar configurações")
        save.setProperty("primary", True)
        save.clicked.connect(self.save_settings)
        form.addRow("", save)
        layout.addWidget(settings_box)

        paths_box = QGroupBox("Pastas portáteis")
        paths_layout = QVBoxLayout(paths_box)
        self.paths_text = QPlainTextEdit()
        self.paths_text.setReadOnly(True)
        self.paths_text.setMaximumHeight(180)
        paths_layout.addWidget(self.paths_text)
        open_folder = QPushButton("Abrir pasta do HERMES")
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR))))
        paths_layout.addWidget(open_folder)
        layout.addWidget(paths_box)
        layout.addStretch()
        return page

    def _configure_timers(self) -> None:
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(self.refresh_runtime)
        self.download_timer = QTimer(self)
        self.download_timer.setInterval(800)
        self.download_timer.timeout.connect(self.refresh_download)
        if not self.smoke_mode:
            self.refresh_timer.start()
            self.download_timer.start()

    def _change_page(self, index: int) -> None:
        if 0 <= index < len(NAV_ITEMS):
            self.pages.setCurrentIndex(index)
            self.page_title.setText(NAV_ITEMS[index])
            if index == 1:
                self.refresh_reports()
            elif index == 2:
                self.refresh_monitor()
            elif index == 3:
                self.refresh_incidents()
            elif index == 4:
                self.refresh_chat()
            elif index == 5:
                self.refresh_knowledge()
            elif index == 6:
                self.refresh_models()
            elif index == 8:
                self.refresh_settings()

    def run_task(
        self,
        function: Callable[[], Any],
        on_result: Callable[[Any], None] | None = None,
        message: str = "Processando…",
    ) -> None:
        worker = Worker(function)
        self._active_tasks += 1
        self.task_progress.show()
        self.status_message.setText(message)
        if on_result is not None:
            worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._show_task_error)
        worker.signals.finished.connect(self._task_finished)
        self.thread_pool.start(worker)

    def _show_task_error(self, message: str) -> None:
        QMessageBox.warning(self, "Operação não concluída", message or "Erro desconhecido.")

    def _task_finished(self) -> None:
        self._active_tasks = max(self._active_tasks - 1, 0)
        if not self._active_tasks:
            self.task_progress.hide()
            self.status_message.setText("Pronto")
        self.refresh_runtime()

    def refresh_all(self) -> None:
        self.refresh_runtime()
        self.refresh_reports()
        self.refresh_monitor()
        self.refresh_incidents()
        self.refresh_chat()
        self.refresh_knowledge()
        self.refresh_models()
        self.refresh_settings()

    def refresh_runtime(self) -> None:
        try:
            metrics = hermes_web.system_metrics()
            if metrics.get("available"):
                cpu = metrics.get("cpu") or {}
                memory = metrics.get("memory") or {}
                disk = metrics.get("disk") or {}
                network = metrics.get("network") or {}
                self.metric_labels["cpu"].setText(f"{float(cpu.get('percent') or 0):.1f}%")
                self.metric_labels["memory"].setText(f"{float(memory.get('percent') or 0):.1f}%")
                self.metric_labels["disk"].setText(f"{float(disk.get('percent') or 0):.1f}%")
                net = float(network.get("sent_bytes_per_second") or 0) + float(
                    network.get("received_bytes_per_second") or 0
                )
                self.metric_labels["network"].setText(f"{format_bytes(net)}/s")
            else:
                for label in self.metric_labels.values():
                    label.setText("—")
            runtime = self.runtime_controller.status()
            profile = runtime["profile"]
            state = STATE_LABELS.get(runtime["state"], runtime["state"])
            self.overview_model.setText(str(profile.get("model") or profile.get("label") or "Sem modelo"))
            self.overview_engine.setText(state)
            self.assistant_state.setText(state)
            self.sidebar_detail.setText(state)
            self.sidebar_state.setText("● ONLINE" if runtime["online"] else "● LOCAL")
            monitor = self.monitor_engine.status()
            self.overview_monitor.setText("Monitor ativo" if monitor["running"] else "Monitor parado")
            self.monitor_state.setText("Monitor ativo" if monitor["running"] else "Monitor parado")
            summary = hermes_incidents.incident_summary()
            self.overview_alerts.setText(
                f"{summary['active']} incidentes ativos • {summary['critical_active']} críticos"
            )
        except Exception as exc:
            self.status_message.setText(f"Atualização parcial: {exc}")

    def run_diagnostic(self, diagnostic_type: str) -> None:
        self.navigation.setCurrentRow(1)
        self.run_task(
            lambda: hermes_web.run_diagnostic(diagnostic_type),
            self._diagnostic_ready,
            "Executando diagnóstico local…",
        )

    def _diagnostic_ready(self, result: Any) -> None:
        self.diagnostic_result.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.refresh_reports()

    def refresh_reports(self) -> None:
        try:
            reports = hermes_web.list_reports()
        except Exception:
            return
        self.reports_table.setRowCount(len(reports))
        for row, report in enumerate(reports):
            summary = report.get("summary") or {}
            filename = report.get("filename")
            self.reports_table.setItem(row, 0, table_item(report.get("completed_at"), filename))
            self.reports_table.setItem(row, 1, table_item(report.get("type")))
            self.reports_table.setItem(row, 2, table_item(summary.get("checks", 0)))
            self.reports_table.setItem(row, 3, table_item(summary.get("alerts", 0)))
            self.reports_table.setItem(row, 4, table_item(filename))

    def _selected_table_data(self, table: QTableWidget, column: int = 0) -> Any:
        rows = table.selectionModel().selectedRows() if table.selectionModel() else []
        if not rows:
            return None
        item = table.item(rows[0].row(), column)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def show_selected_report(self) -> None:
        filename = self._selected_table_data(self.reports_table)
        if not filename:
            return
        try:
            report = hermes_web.read_report(str(filename))
        except Exception as exc:
            self.diagnostic_result.setPlainText(str(exc))
            return
        self._current_report = str(filename)
        self.diagnostic_result.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))

    def export_report_html(self) -> None:
        filename = self._current_report or self._selected_table_data(self.reports_table)
        if not filename:
            QMessageBox.information(self, "Relatório", "Selecione um relatório.")
            return
        try:
            report = hermes_web.read_report(str(filename))
            content = hermes_web.report_to_html(str(filename), report)
        except Exception as exc:
            QMessageBox.warning(self, "Relatório", str(exc))
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório HTML",
            str(REPORT_DIR / (Path(str(filename)).stem + ".html")),
            "HTML (*.html)",
        )
        if target:
            Path(target).write_text(content, encoding="utf-8")
            self.status_message.setText(f"Relatório exportado: {target}")

    def start_monitor(self) -> None:
        try:
            self.monitor_engine.start()
        except Exception as exc:
            QMessageBox.warning(self, "Monitor", str(exc))
        self.refresh_monitor()

    def stop_monitor(self) -> None:
        try:
            self.monitor_engine.stop()
        except Exception as exc:
            QMessageBox.warning(self, "Monitor", str(exc))
        self.refresh_monitor()

    def refresh_monitor(self) -> None:
        try:
            config = hermes_monitor.load_monitor_config()
            index = self.monitor_interval.findData(config["interval_seconds"])
            if index >= 0:
                self.monitor_interval.setCurrentIndex(index)
            for resource, (warning, critical) in self.monitor_thresholds.items():
                warning.setValue(int(config[f"{resource}_warning"]))
                critical.setValue(int(config[f"{resource}_critical"]))
            alerts = hermes_monitor.list_alerts(100)
            self.alerts_table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                alert_id = alert.get("id")
                state = "Resolvido" if alert.get("resolved_at") else ("Visto" if alert.get("acknowledged") else "Ativo")
                self.alerts_table.setItem(row, 0, table_item(alert.get("detected_at"), alert_id))
                self.alerts_table.setItem(row, 1, table_item(alert.get("resource")))
                self.alerts_table.setItem(row, 2, table_item(SEVERITY_LABELS.get(str(alert.get("severity")), alert.get("severity"))))
                self.alerts_table.setItem(row, 3, table_item(f"{alert.get('last_value', 0)}%"))
                self.alerts_table.setItem(row, 4, table_item(state))
                self.alerts_table.setItem(row, 5, table_item(alert.get("message")))
            status = self.monitor_engine.status()
            self.monitor_state.setText("Monitor ativo" if status["running"] else "Monitor parado")
        except Exception as exc:
            self.status_message.setText(f"Monitor: {exc}")

    def save_monitor_settings(self) -> None:
        updates: dict[str, Any] = {"interval_seconds": self.monitor_interval.currentData()}
        for resource, (warning, critical) in self.monitor_thresholds.items():
            updates[f"{resource}_warning"] = warning.value()
            updates[f"{resource}_critical"] = critical.value()
        try:
            hermes_monitor.save_monitor_config(updates)
        except Exception as exc:
            QMessageBox.warning(self, "Limites inválidos", str(exc))
            return
        self.status_message.setText("Configurações do monitor salvas.")

    def acknowledge_alert(self) -> None:
        alert_id = self._selected_table_data(self.alerts_table)
        if not alert_id:
            QMessageBox.information(self, "Alerta", "Selecione um alerta.")
            return
        try:
            hermes_monitor.acknowledge_alerts(str(alert_id))
        except Exception as exc:
            QMessageBox.warning(self, "Alerta", str(exc))
        self.refresh_monitor()

    def incident_from_alert(self) -> None:
        alert_id = self._selected_table_data(self.alerts_table)
        if not alert_id:
            QMessageBox.information(self, "Alerta", "Selecione um alerta.")
            return
        try:
            alert = hermes_monitor.get_alert(str(alert_id))
            snapshot = hermes_web.incident_snapshot()
            snapshot["alert"] = alert
            incident = hermes_incidents.create_from_alert(alert, snapshot)
        except Exception as exc:
            QMessageBox.warning(self, "Incidente", str(exc))
            return
        self.navigation.setCurrentRow(3)
        self.refresh_incidents(select_id=incident["id"])

    def new_incident(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Novo incidente")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        title = QLineEdit()
        severity = QComboBox()
        severity.addItem("Normal", "normal")
        severity.addItem("Atenção", "attention")
        severity.addItem("Crítico", "critical")
        severity.setCurrentIndex(1)
        description = QPlainTextEdit()
        description.setMaximumHeight(150)
        form.addRow("Título", title)
        form.addRow("Severidade", severity)
        form.addRow("Descrição", description)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            incident = hermes_incidents.create_incident(
                title.text(),
                severity.currentData(),
                description.toPlainText(),
                snapshot=hermes_web.incident_snapshot(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Incidente", str(exc))
            return
        self.navigation.setCurrentRow(3)
        self.refresh_incidents(select_id=incident["id"])

    def refresh_incidents(self, select_id: str | None = None) -> None:
        try:
            payload = hermes_incidents.dashboard_payload()
        except Exception:
            return
        summary = payload["summary"]
        self.incident_summary_label.setText(
            f"{summary['active']} ativos • {summary['critical_active']} críticos • {summary['resolved']} resolvidos"
        )
        incidents = payload["incidents"]
        self.incidents_table.setRowCount(len(incidents))
        target_row = -1
        for row, incident in enumerate(incidents):
            incident_id = incident.get("id")
            self.incidents_table.setItem(row, 0, table_item(STATUS_LABELS.get(str(incident.get("status")), incident.get("status")), incident_id))
            self.incidents_table.setItem(row, 1, table_item(SEVERITY_LABELS.get(str(incident.get("severity")), incident.get("severity"))))
            self.incidents_table.setItem(row, 2, table_item(incident.get("title")))
            self.incidents_table.setItem(row, 3, table_item(incident.get("updated_at")))
            if select_id and incident_id == select_id:
                target_row = row
        if target_row >= 0:
            self.incidents_table.selectRow(target_row)

    def show_selected_incident(self) -> None:
        incident_id = self._selected_table_data(self.incidents_table)
        if not incident_id:
            return
        try:
            incident = hermes_incidents.get_incident(str(incident_id))
        except Exception as exc:
            self.status_message.setText(str(exc))
            return
        self._current_incident_id = str(incident_id)
        self._incident_syncing = True
        self.incident_title.setText(str(incident.get("title")))
        self.incident_meta.setText(
            f"{SEVERITY_LABELS.get(str(incident.get('severity')), incident.get('severity'))} • "
            f"criado em {incident.get('created_at')}"
        )
        index = self.incident_status.findData(incident.get("status"))
        if index >= 0:
            self.incident_status.setCurrentIndex(index)
        self.incident_checklist.clear()
        for entry in incident.get("checklist", []):
            item = QListWidgetItem(str(entry.get("label")))
            item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if entry.get("completed") else Qt.CheckState.Unchecked)
            self.incident_checklist.addItem(item)
        timeline = "\n\n".join(
            f"{event.get('created_at')}\n{event.get('message')}" for event in incident.get("timeline", [])
        )
        self.incident_timeline.setPlainText(timeline)
        self._incident_syncing = False

    def change_incident_status(self) -> None:
        if self._incident_syncing or not self._current_incident_id:
            return
        try:
            hermes_incidents.update_status(self._current_incident_id, self.incident_status.currentData())
        except Exception as exc:
            QMessageBox.warning(self, "Incidente", str(exc))
        self.refresh_incidents(select_id=self._current_incident_id)

    def toggle_checklist_item(self, item: QListWidgetItem) -> None:
        if self._incident_syncing or not self._current_incident_id:
            return
        try:
            hermes_incidents.set_checklist_item(
                self._current_incident_id,
                str(item.data(Qt.ItemDataRole.UserRole)),
                item.checkState() == Qt.CheckState.Checked,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Checklist", str(exc))
        self.refresh_incidents(select_id=self._current_incident_id)

    def add_incident_note(self) -> None:
        if not self._current_incident_id:
            return
        text, accepted = QInputDialog.getMultiLineText(self, "Adicionar nota", "Nota defensiva")
        if not accepted or not text.strip():
            return
        try:
            hermes_incidents.add_note(self._current_incident_id, text)
        except Exception as exc:
            QMessageBox.warning(self, "Nota", str(exc))
        self.refresh_incidents(select_id=self._current_incident_id)

    def analyse_incident(self) -> None:
        if not self._current_incident_id:
            return
        incident_id = self._current_incident_id

        def task() -> str:
            if not port_is_open():
                self.runtime_controller.start()
            incident = hermes_incidents.get_incident(incident_id)
            started = time.monotonic()
            answer = hermes_web.ask_llama(hermes_incidents.analysis_prompt(incident), "deep")
            hermes_incidents.add_analysis(incident_id, answer, duration_seconds=time.monotonic() - started)
            return answer

        self.run_task(task, lambda _result: self.refresh_incidents(select_id=incident_id), "Analisando incidente…")

    def export_incident(self, kind: str) -> None:
        if not self._current_incident_id:
            QMessageBox.information(self, "Incidente", "Selecione um incidente.")
            return
        incident = hermes_incidents.get_incident(self._current_incident_id)
        extension = "pdf" if kind == "pdf" else "html"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar incidente",
            str(REPORT_DIR / f"incidente-{self._current_incident_id[:8]}.{extension}"),
            "PDF (*.pdf)" if kind == "pdf" else "HTML (*.html)",
        )
        if not target:
            return
        if kind == "pdf":
            Path(target).write_bytes(hermes_incidents.incident_pdf(incident))
        else:
            Path(target).write_text(hermes_incidents.incident_html(incident), encoding="utf-8")
        self.status_message.setText(f"Incidente exportado: {target}")

    def refresh_chat(self) -> None:
        try:
            history = load_chat_history()
        except Exception:
            history = []
        blocks: list[str] = []
        for message in history:
            role = "Você" if message.get("role") == "user" else "HERMES"
            color = "#4ed9ff" if role == "HERMES" else "#91b0ca"
            content = str(message.get("content", "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            content = content.replace("\n", "<br>")
            blocks.append(
                f"<div style='margin:10px 0;padding:12px;border:1px solid #29445d;border-radius:8px;background:#0b1a29'>"
                f"<b style='color:{color}'>{role}</b><div style='margin-top:7px'>{content}</div></div>"
            )
        self.chat_history.setHtml("".join(blocks) or "<p style='color:#8fa6bd'>O histórico local está vazio.</p>")
        self.chat_history.verticalScrollBar().setValue(self.chat_history.verticalScrollBar().maximum())

    def send_chat(self) -> None:
        prompt = self.chat_input.toPlainText().strip()
        if not prompt:
            return
        mode = str(self.assistant_mode.currentData())
        self.chat_input.clear()

        def task() -> str:
            if not port_is_open():
                self.runtime_controller.start()
            answer = hermes_web.ask_llama(prompt, mode)
            append_chat_exchange(prompt, answer, mode)
            return answer

        self.run_task(task, lambda _answer: self.refresh_chat(), "Consultando a IA local…")

    def clear_chat(self) -> None:
        if QMessageBox.question(self, "Limpar histórico", "Remover o histórico local de conversa?") != QMessageBox.StandardButton.Yes:
            return
        clear_chat_history()
        self.refresh_chat()

    def start_ai(self) -> None:
        self.run_task(self.runtime_controller.start, lambda _result: self.refresh_models(), "Iniciando llama.cpp…")

    def stop_ai(self) -> None:
        self.run_task(self.runtime_controller.stop, lambda _result: self.refresh_models(), "Encerrando IA local…")

    def refresh_knowledge(self) -> None:
        try:
            collections = hermes_knowledge.list_collections()
            current = self.knowledge_collection.currentData()
            self.knowledge_collection.blockSignals(True)
            self.knowledge_collection.clear()
            self.knowledge_collection.addItem("Todas as coleções", None)
            for collection in collections:
                self.knowledge_collection.addItem(
                    f"{collection['name']} ({collection['document_count']})",
                    collection["id"],
                )
            index = self.knowledge_collection.findData(current)
            self.knowledge_collection.setCurrentIndex(max(index, 0))
            self.knowledge_collection.blockSignals(False)
            documents = hermes_knowledge.list_documents()
            self.knowledge_documents.setRowCount(len(documents))
            for row, document in enumerate(documents):
                document_id = document.get("id")
                self.knowledge_documents.setItem(row, 0, table_item(document.get("title"), document_id))
                self.knowledge_documents.setItem(row, 1, table_item(document.get("collection_name")))
                self.knowledge_documents.setItem(row, 2, table_item(format_bytes(document.get("size_bytes"))))
                self.knowledge_documents.setItem(row, 3, table_item(document.get("created_at")))
        except Exception as exc:
            self.status_message.setText(f"Base Local: {exc}")

    def create_knowledge_collection(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nova coleção", "Nome da coleção")
        if not accepted or not name.strip():
            return
        try:
            collection = hermes_knowledge.create_collection(name)
        except Exception as exc:
            QMessageBox.warning(self, "Coleção", str(exc))
            return
        self.refresh_knowledge()
        index = self.knowledge_collection.findData(collection["id"])
        if index >= 0:
            self.knowledge_collection.setCurrentIndex(index)

    def import_knowledge_document(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar documento",
            str(APP_DIR),
            "Documentos suportados (*.txt *.md *.json *.log)",
        )
        if not path:
            return
        collection_id = self.knowledge_collection.currentData() or hermes_knowledge.DEFAULT_COLLECTION_ID

        def task() -> dict[str, Any]:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return hermes_knowledge.add_document(Path(path).name, content, str(collection_id))

        self.run_task(task, lambda _result: self.refresh_knowledge(), "Indexando documento local…")

    def delete_knowledge_document(self) -> None:
        document_id = self._selected_table_data(self.knowledge_documents)
        if not document_id:
            QMessageBox.information(self, "Base Local", "Selecione um documento.")
            return
        if QMessageBox.question(self, "Excluir documento", "Remover o documento da Base Local?") != QMessageBox.StandardButton.Yes:
            return
        try:
            hermes_knowledge.delete_document(str(document_id))
        except Exception as exc:
            QMessageBox.warning(self, "Base Local", str(exc))
        self.refresh_knowledge()

    def search_knowledge(self) -> None:
        query = self.knowledge_query.text().strip()
        if not query:
            return
        collection = self.knowledge_collection.currentData()
        try:
            result = hermes_knowledge.search_knowledge(
                query,
                [collection] if collection else None,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Pesquisa local", str(exc))
            return
        self._knowledge_last = result
        if not result["results"]:
            self.knowledge_results.setPlainText("Nenhuma fonte local encontrada.")
            return
        blocks = []
        for entry in result["results"]:
            blocks.append(
                f"[{entry['source_number']}] {entry['title']} — {entry['collection_name']}\n"
                f"{entry['snippet']}"
            )
        self.knowledge_results.setPlainText("\n\n".join(blocks))

    def ask_knowledge(self) -> None:
        question = self.knowledge_query.text().strip()
        if not question:
            return
        self.search_knowledge()
        result = self._knowledge_last
        if not result or not result.get("results"):
            return

        def task() -> str:
            if not port_is_open():
                self.runtime_controller.start()
            return hermes_web.ask_llama(
                hermes_knowledge.knowledge_answer_prompt(question, result["results"]),
                "deep",
            )

        def ready(answer: Any) -> None:
            sources = self.knowledge_results.toPlainText()
            self.knowledge_results.setPlainText(f"RESPOSTA\n\n{answer}\n\nFONTES RECUPERADAS\n\n{sources}")

        self.run_task(task, ready, "Consultando a IA com fontes locais…")

    def refresh_models(self) -> None:
        try:
            status = self.runtime_controller.status()
            profile = status["profile"]
            self.model_name.setText(str(profile.get("model") or "Nenhum modelo configurado"))
            path = str(profile.get("model_path") or "—")
            size = ""
            try:
                model_path = Path(path)
                if model_path.is_file():
                    size = f" • {format_bytes(model_path.stat().st_size)}"
            except OSError:
                pass
            self.model_path.setText(f"{path}{size}")
            llama = status.get("llama") or {}
            engine = llama.get("executable") or "não configurado"
            self.model_engine.setText(f"llama.cpp: {engine} • {STATE_LABELS.get(status['state'], status['state'])}")
        except Exception as exc:
            self.model_engine.setText(str(exc))
        self.refresh_download()

    def choose_custom_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Adicionar modelo GGUF", str(MODELS_DIR), "Modelos GGUF (*.gguf)")
        if not path:
            return
        copy_model = self.copy_model_checkbox.isChecked()
        overwrite = False
        if copy_model and (MODELS_DIR / Path(path).name).exists() and (MODELS_DIR / Path(path).name).resolve() != Path(path).resolve():
            answer = QMessageBox.question(
                self,
                "Arquivo existente",
                "Já existe um modelo com esse nome. Substituir após validar a nova cópia?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        self.run_task(
            lambda: register_custom_model(path, copy_to_portable=copy_model, overwrite=overwrite),
            lambda _result: self.refresh_models(),
            "Validando e registrando modelo…",
        )

    def choose_llama(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Localizar llama.cpp",
            str(APP_DIR),
            "llama.cpp (llama-server.exe llama.exe);;Executáveis (*.exe);;Todos os arquivos (*)",
        )
        if not path:
            return
        try:
            register_llama_executable(path)
        except Exception as exc:
            QMessageBox.warning(self, "llama.cpp", str(exc))
            return
        self.refresh_models()

    def start_model_download(self) -> None:
        try:
            hermes_models.start_model_download(str(self.preset_combo.currentData()))
        except Exception as exc:
            QMessageBox.warning(self, "Download", str(exc))
        self.refresh_download()

    def cancel_model_download(self) -> None:
        try:
            hermes_models.cancel_model_download()
        except Exception as exc:
            QMessageBox.information(self, "Download", str(exc))
        self.refresh_download()

    def refresh_download(self) -> None:
        try:
            state = hermes_models.download_snapshot()
        except Exception:
            return
        percent = state.get("percent")
        status = str(state.get("status") or "idle")
        changed = status != self._last_download_status
        self._last_download_status = status
        self.download_progress.setValue(int(float(percent or 0) * 10))
        downloaded = format_bytes(state.get("downloaded_bytes"))
        total = format_bytes(state.get("total_bytes")) if state.get("total_bytes") else "tamanho desconhecido"
        self.download_state.setText(f"{state.get('message')} • {downloaded} de {total}")
        if status == "completed" and changed:
            QTimer.singleShot(0, self.refresh_models)

    def create_backup(self) -> None:
        try:
            filename, content, manifest = hermes_backup.create_backup()
        except Exception as exc:
            QMessageBox.warning(self, "Backup", str(exc))
            return
        target, _ = QFileDialog.getSaveFileName(self, "Salvar backup", str(APP_DIR / filename), "ZIP (*.zip)")
        if not target:
            return
        Path(target).write_bytes(content)
        self.backup_result.setPlainText(
            f"Backup criado com sucesso.\n\nArquivo: {target}\nTamanho: {format_bytes(len(content))}\n"
            f"Itens: {len(manifest.get('files', []))}\nCriado em: {manifest.get('created_at')}"
        )

    def restore_backup(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Selecionar backup do HERMES", str(APP_DIR), "ZIP (*.zip)")
        if not source:
            return
        try:
            content = Path(source).read_bytes()
            inspection = hermes_backup.inspect_backup(content)
        except Exception as exc:
            QMessageBox.warning(self, "Backup inválido", str(exc))
            return
        answer = QMessageBox.question(
            self,
            "Confirmar restauração",
            f"O backup contém {inspection['file_count']} arquivos. Restaurar os dados validados?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = hermes_backup.restore_backup(content)
        except Exception as exc:
            QMessageBox.warning(self, "Restauração", str(exc))
            return
        self.backup_result.setPlainText(
            f"Restauração concluída.\n\nArquivos restaurados: {result['restored_count']}\n"
            + "\n".join(result.get("restored", []))
        )
        self.refresh_all()

    def refresh_settings(self) -> None:
        config = load_config()
        for combo, value in (
            (self.settings_profile, config["profile"]),
            (self.settings_mode, config["default_mode"]),
            (self.settings_context, config["context_size"]),
        ):
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.settings_threads.setValue(int(config["threads"]))
        self.settings_gpu.setValue(int(config["gpu_layers"]))
        self.paths_text.setPlainText(json.dumps(runtime_path_payload(), ensure_ascii=False, indent=2))

    def save_settings(self) -> None:
        try:
            save_config(
                {
                    "profile": self.settings_profile.currentData(),
                    "default_mode": self.settings_mode.currentData(),
                    "context_size": self.settings_context.currentData(),
                    "threads": self.settings_threads.value(),
                    "gpu_layers": self.settings_gpu.value(),
                }
            )
        except Exception as exc:
            QMessageBox.warning(self, "Configurações", str(exc))
            return
        self.status_message.setText("Configurações salvas. Reinicie a IA para aplicar mudanças.")
        self.refresh_models()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.refresh_timer.stop()
        self.download_timer.stop()
        try:
            self.monitor_engine.stop(persist_enabled=False)
        except Exception:
            pass
        try:
            self.runtime_controller.stop()
        except Exception:
            pass
        event.accept()


def _install_exception_dialog() -> None:
    original = sys.excepthook

    def handler(exc_type: type[BaseException], exc: BaseException, traceback: Any) -> None:
        original(exc_type, exc, traceback)
        try:
            QMessageBox.critical(None, "Erro inesperado", f"O HERMES encontrou um erro:\n\n{exc}")
        except Exception:
            pass

    sys.excepthook = handler


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("HERMES")
    app.setFont(QFont("Segoe UI", 10))
    return app


def run_smoke_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    ensure_runtime_directories()
    app = create_application([sys.argv[0], "--smoke-test"])
    window = MainWindow(smoke_mode=True)
    app.processEvents()
    payload = startup_payload()
    if not payload.get("desktop") or payload.get("browser_required"):
        return 2
    if window.pages.count() != len(NAV_ITEMS):
        return 3
    window.close()
    app.processEvents()
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HERMES Security Desktop")
    parser.add_argument("--smoke-test", action="store_true", help="valida o executável sem mostrar a janela")
    parser.add_argument("--skip-wizard", action="store_true", help="ignora o assistente inicial nesta execução")
    args = parser.parse_args(argv)
    if args.smoke_test:
        return run_smoke_test()

    ensure_runtime_directories()
    app = create_application([sys.argv[0]])
    _install_exception_dialog()
    payload = startup_payload()
    if payload["setup_required"] and not args.skip_wizard:
        wizard = FirstRunWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return 0
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
