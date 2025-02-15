########################################
# imports
########################################
import sys
import os
import time
from typing import List
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QTableWidgetItem, QGraphicsScene
from PyQt5.QtCore import QThreadPool, QRectF, Qt, QRegExp
from PyQt5.QtGui import QIcon, QPen, QRegExpValidator
from ui_py.gui import Ui_MainWindow

from utils.data.plc import data_to_plc
from utils.workers_coord_filter import *
from utils.qt_utils import qt_create_table
from test.test import test_file
########################################


class CoordFilter(QMainWindow):
    def __init__(self):
        super(CoordFilter, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.trigger_a1: bool = False
        self.trigger_a2: bool = False
        self.trigger_b1: bool = False
        self.trigger_b2: bool = False
        self.code_read: str = ""
        self.side_string: str = ""
        #######################################
        # Thread
        #######################################
        self.mythread_plc = QThreadPool()
        self.mythread_test = QThreadPool()
        self.mythread_bcscanner = QThreadPool()

        self.myworker_plc = Worker_PLC()
        self.myworker_test = Worker_Test()
        self.myworker_bcscanner = Worker_BarCodeScanner()

        self.myworker_plc.signal_worker.result_multiples.connect(self.plc_routine)
        self.myworker_plc.signal_worker.error.connect(self.runnable_error_plc)  # signal when we have a plc comm error
        self.myworker_test.signal_worker_test.result.connect(self.start_test)
        self.myworker_test.signal_worker_test.error.connect(self.runnable_error_test)  # signal when we have a plc comm error
        self.myworker_bcscanner.signal.result_list.connect(self.bar_code_scanner_result)
        #####################################################################
        # Button call function to start test of filter positions with a file
        #####################################################################
        self.mythread_plc.start(self.myworker_plc)
        self.mythread_test.start(self.myworker_test)
        self.mythread_bcscanner.start(self.myworker_bcscanner)
        #########################################################################
        # Initial Settings
        #########################################################################
        self.ui.ico_local_file.setEnabled(False)
        self.ui.ico_test_file.setEnabled(False)
        #########################################################################
        # Signal and values to input limits
        #########################################################################
        self.test_file_selected = False
        self.inputting_values = False
        self.limit_dist_xyz = float(self.ui.le_var_dist_pts.text())
        self.limit_c = float(self.ui.le_var_c.text())
        self.limit_d = float(self.ui.le_var_d.text())
        self.limit_h = float(self.ui.le_var_h.text())
        self.limit_p = float(self.ui.le_var_p.text())
        #########################################################################
        # Setting RegEx to LineEdits
        #########################################################################
        self.regex = QRegExp(r"[0-9]?[0-9]?\.[0-9][0-9]?")
        self.validator = QRegExpValidator(self.regex)
        self.ui.le_var_dist_pts.setValidator(self.validator)
        self.ui.le_var_c.setValidator(self.validator)
        self.ui.le_var_d.setValidator(self.validator)
        self.ui.le_var_h.setValidator(self.validator)
        self.ui.le_var_p.setValidator(self.validator)
        #########################################################################
        # Signal that the transfer is ON
        #########################################################################
        self.transferring_data = False
        #########################################################################
        self.ui.rb_cloud_file.toggled.connect(self.set_cloud_file)
        self.ui.rb_local_file.toggled.connect(self.set_local_file)

        self.ui.rb_plc.toggled.connect(self.set_file_to_plc)
        self.ui.rb_test.toggled.connect(self.set_file_to_test)

        self.ui.btn_search_file.clicked.connect(self.search_folder)

        self.ui.btn_search_file_for_test.clicked.connect(self.search_file_for_test)
        self.ui.btn_test_file.clicked.connect(self.test_routine)

        self.ui.btn_input_values.clicked.connect(self.input_values)
        ##################################
        # Variables used to test a file
        ##################################
        self.test_signal: bool = False
        self.list_pos_x: List[float] = []
        self.list_pos_y: List[float] = []
        self.list_pos_z: List[float] = []
        self.list_pos_c: List[float] = []
        self.list_pos_d: List[float] = []
        self.list_pos: List[int] = []
        self.list_pos_info: List[str] = []
        #######################################
        # Create graphic
        #######################################
        # Defining a scene rect of 400x200, with it's origin at 0,0.
        # If we don't set this on creation, we can set it later with .setSceneRect
        self.scene = QGraphicsScene(-70, -41, 140, 82)
        self.ui.graphicsView.setScene(self.scene)
        self.ui.graphicsView.scale(3, 3)
        self.ui.tbl_positions.horizontalHeader().setVisible(False)
        self.ui.tbl_positions.verticalHeader().setVisible(False)

    def set_cloud_file(self):
        self.ui.btn_search_file.setEnabled(False)
        self.ui.le_file_path.setEnabled(False)
        self.ui.ico_local_file.setEnabled(False)
        self.ui.ico_cloud.setEnabled(True)

    def set_local_file(self):
        self.ui.btn_search_file.setEnabled(True)
        self.ui.le_file_path.setEnabled(True)
        self.ui.ico_local_file.setEnabled(True)
        self.ui.ico_cloud.setEnabled(False)

    def set_file_to_plc(self):
        self.ui.btn_search_file_for_test.setEnabled(False)
        self.ui.le_file_for_test.setEnabled(False)
        self.ui.btn_test_file.setEnabled(False)
        self.ui.btn_input_values.setEnabled(False)
        self.ui.ico_test_file.setEnabled(False)
        self.ui.ico_plc.setEnabled(True)

    def set_file_to_test(self):
        self.ui.btn_search_file_for_test.setEnabled(True)
        self.ui.le_file_for_test.setEnabled(True)
        if self.test_file_selected:
            self.ui.btn_test_file.setEnabled(True)
        else:
            self.ui.btn_test_file.setEnabled(False)
        self.ui.btn_input_values.setEnabled(True)
        self.ui.ico_test_file.setEnabled(True)
        self.ui.ico_plc.setEnabled(False)

    def input_values(self):
        if self.inputting_values:
            self.inputting_values = False
            self.ui.btn_input_values.setText("Mudar\nvalores")
            self.ui.btn_test_file.setEnabled(True)

            self.ui.le_var_dist_pts.setEnabled(False)
            self.ui.le_var_c.setEnabled(False)
            self.ui.le_var_d.setEnabled(False)
            self.ui.le_var_h.setEnabled(False)
            self.ui.le_var_p.setEnabled(False)

            if not self.ui.le_var_dist_pts.text():
                self.ui.le_var_dist_pts.setText(self.limit_dist_xyz)
            else:
                self.limit_dist_xyz = float(self.ui.le_var_dist_pts.text())

            if not self.ui.le_var_c.text():
                self.ui.le_var_c.setText(self.limit_c)
            else:
                self.limit_c = float(self.ui.le_var_c.text())

            if not self.ui.le_var_d.text():
                self.ui.le_var_d.setText(self.limit_d)
            else:
                self.limit_d = float(self.ui.le_var_d.text())

            if not self.ui.le_var_h.text():
                self.ui.le_var_h.setText(self.limit_h)
            else:
                self.limit_h = float(self.ui.le_var_h.text())

            if not self.ui.le_var_p.text():
                self.ui.le_var_p.setText(self.limit_p)
            else:
                self.limit_p = float(self.ui.le_var_p.text())

        else:
            self.inputting_values = True
            self.ui.btn_input_values.setText("Confirmar\nmudança")
            self.ui.btn_test_file.setEnabled(False)
            self.ui.le_var_dist_pts.setEnabled(True)
            self.ui.le_var_c.setEnabled(True)
            self.ui.le_var_d.setEnabled(True)
            self.ui.le_var_h.setEnabled(True)
            self.ui.le_var_p.setEnabled(True)

    def start_test(self):
        self.test_signal = True

    def search_folder(self):
        path_name = QFileDialog.getExistingDirectory(self, "Selecione um arquivo", os.getcwd())
        self.ui.le_file_path.setText(path_name)

    def search_file_for_test(self):
        path_file_name = QFileDialog.getOpenFileName(self, "Selecione um arquivo", os.getcwd(), "*.csv")
        self.ui.le_file_for_test.setText(path_file_name[0])
        if self.ui.le_file_for_test.text():
            self.test_file_selected = True
            self.ui.btn_test_file.setEnabled(True)

    def bar_code_scanner_result(self, list_bcscanner):
        self.code_read, self.side_string = list_bcscanner

        if self.side_string == "A1":
            self.trigger_a1 = True
        elif self.side_string == "A2":
            self.trigger_a2 = True
        elif self.side_string == "B1":
            self.trigger_b1 = True
        elif self.side_string == "B2":
            self.trigger_b2 = True

    def plc_routine(self, configpontos, data_ctrl_a1, data_ctrl_a2, data_ctrl_b1, data_ctrl_b2, HMI):
        print('- Comunicação de dados utilizando Python com CLP Rockwell')
        print(f"------ Leitura do código: {self.code_read}")

        if self.ui.rb_plc.isChecked():
            ##############################################
            # Wait trigger A1
            ##############################################
            try:
                if (self.trigger_a1 or data_ctrl_a1["Trigger"]) and not self.transferring_data:
                    self.transferring_data = True
                    data_to_plc(data_ctrl_a1,
                                'CutDepthA1',
                                HMI['EnableLog'],
                                HMI['NumPosMax'],
                                configpontos,
                                'DataCtrl_A1',
                                self.ui.rb_cloud_file.isChecked(),
                                self.ui.rb_local_file.isChecked(),
                                self.ui.le_file_path.text(),
                                self.ui,
                                self.scene,
                                self.code_read)
            except Exception as e:
                print(f'{e} - trying to read DataCtrl_A1')
            ##############################################
            # Wait trigger A2
            ##############################################
            try:
                if (self.trigger_a2 or data_ctrl_a2["Trigger"]) and not self.transferring_data:
                    self.transferring_data = True
                    data_to_plc(data_ctrl_a2,
                                'CutDepthA2',
                                HMI['EnableLog'],
                                HMI['NumPosMax'],
                                configpontos,
                                'DataCtrl_A2',
                                self.ui.rb_cloud_file.isChecked(),
                                self.ui.rb_local_file.isChecked(),
                                self.ui.le_file_path.text(),
                                self.ui,
                                self.scene,
                                self.code_read)
            except Exception as e:
                print(f'{e} - trying to read DataCtrl_A2')
            ##############################################
            # Wait trigger B1
            ##############################################
            try:
                if (self.trigger_b1 or data_ctrl_b1["Trigger"]) and not self.transferring_data:
                    self.transferring_data = True
                    data_to_plc(data_ctrl_b1,
                                'CutDepthB1',
                                HMI['EnableLog'],
                                HMI['NumPosMax'],
                                configpontos,
                                'DataCtrl_B1',
                                self.ui.rb_cloud_file.isChecked(),
                                self.ui.rb_local_file.isChecked(),
                                self.ui.le_file_path.text(),
                                self.ui,
                                self.scene,
                                self.code_read)
            except Exception as e:
                print(f'{e} - trying to read DataCtrl_B1')
            ##############################################
            # Wait trigger B2
            ##############################################
            try:
                if (self.trigger_b2 or data_ctrl_b2["Trigger"]) and not self.transferring_data:
                    self.transferring_data = True
                    data_to_plc(data_ctrl_b2,
                                'CutDepthB2',
                                HMI['EnableLog'],
                                HMI['NumPosMax'],
                                configpontos,
                                'DataCtrl_B2',
                                self.ui.rb_cloud_file.isChecked(),
                                self.ui.rb_local_file.isChecked(),
                                self.ui.le_file_path.text(),
                                self.ui,
                                self.scene,
                                self.code_read)
            except Exception as e:
                print(f'{e} - trying to read DataCtrl_B2')

            self.transferring_data = False
            self.trigger_a1 = False
            self.trigger_a2 = False
            self.trigger_b1 = False
            self.trigger_b2 = False
            self.code_read = ""

    def test_routine(self, signal):

        file_path: str = ''

        if self.ui.rb_test.isChecked() and len(self.ui.le_file_for_test.text()) > 0 and self.test_signal:
            #######################################
            # Limpa a tabela de posições
            #######################################
            self.ui.tbl_positions.clear()
            #######################################
            # Disable test button on the gui
            #######################################
            self.ui.btn_test_file.setEnabled(False)
            #############################################
            # Set file path from the line edit on the gui
            #############################################
            file_path = self.ui.le_file_for_test.text()
            ###############################################
            print("Inicio da execução do teste de filtros")
            ###############################################
            test_file(file_path, self.list_pos_x, self.list_pos_y, self.list_pos_z, self.list_pos_c, self.list_pos_d,
                      self.list_pos, self.list_pos_info, self.limit_d, self.limit_c, self.limit_dist_xyz, self.limit_h,
                      self.limit_p)
            #######################################
            for n in range(self.ui.tbl_positions.rowCount()):
                self.ui.tbl_positions.removeRow(n)

            self.scene.clear()
            self.ui.graphicsView.scene().clear()
            self.ui.graphicsView.update()

            qt_create_table(self.ui.tbl_positions,
                            7,
                            len(self.list_pos))

            for i in range(len(self.list_pos)):
                self.ui.tbl_positions.setItem(i, 0, QTableWidgetItem(str(self.list_pos[i])))
                self.ui.tbl_positions.setItem(i, 1, QTableWidgetItem(str(self.list_pos_x[i])))
                self.ui.tbl_positions.setItem(i, 2, QTableWidgetItem(str(self.list_pos_y[i])))
                self.ui.tbl_positions.setItem(i, 3, QTableWidgetItem(str(self.list_pos_z[i])))
                self.ui.tbl_positions.setItem(i, 4, QTableWidgetItem(str(self.list_pos_c[i])))
                self.ui.tbl_positions.setItem(i, 5, QTableWidgetItem(str(self.list_pos_d[i])))
                self.ui.tbl_positions.setItem(i, 6, QTableWidgetItem(str(self.list_pos_info[i])))
                self.ui.tbl_positions.resizeColumnsToContents()

                self.scene.addEllipse(QRectF(self.list_pos_x[i], self.list_pos_y[i], 0.2, 0.2), QPen(Qt.blue))

            self.ui.graphicsView.update()
            self.ui.graphicsView.show()

            #######################################
            # Enable test button on the gui
            #######################################
            self.ui.btn_test_file.setEnabled(True)
            #######################################
            # Set the test signal to False
            #######################################
            self.test_signal = False
            #######################################

        elif len(self.ui.le_file_for_test.text()) <= 0:
            print("Selecione um arquivo")
            #######################################
            # Set the test signal to False
            #######################################
            self.test_signal = False
            #######################################

    def runnable_error_plc(self):
        if self.ui.rb_plc.isChecked():
            print("Erro no worker de envio de dados para o CLP")

    def runnable_error_test(self):
        if self.ui.rb_teste.isChecked():
            print("Erro no worker para o teste de arquivo local")

    def stop_threads(self):
        print("Finalizando Threads")
        try:
            self.myworker_plc.stop()
            self.myworker_test.stop()
            self.myworker_bcscanner.stop()
        except Exception as e:
            print(f"{e} -> main.py - stop_threads")
        print("Threads finalizadas")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = CoordFilter()
    main_win.show()
    main_win.setWindowIcon(QIcon("./assets/rn.ico"))
    app.aboutToQuit.connect(main_win.stop_threads)
    sys.exit(app.exec_())





