import logging
import os
from typing import Annotated, Optional

import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

import qt 

from DICOMLib import DICOMUtils 
from functools import partial

import ctk 
import numpy as np 

import requests 

import pydicom 

#
# SlicerMRClass
#


class SlicerMRClass(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("SlicerMRClass")  # TODO: make this more human readable by adding spaces
        # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Examples")]
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["John Doe (AnyWare Corp.)"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#SlicerMRClass">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")

        # Additional initialization step after application startup is complete
        slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#


def registerSampleData():
    """Add data sets to Sample Data module."""
    # It is always recommended to provide sample data for users to make it easy to try the module,
    # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

    import SampleData

    iconsPath = os.path.join(os.path.dirname(__file__), "Resources/Icons")

    # To ensure that the source code repository remains small (can be downloaded and installed quickly)
    # it is recommended to store data sets that are larger than a few MB in a Github release.

    # SlicerMRClass1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="SlicerMRClass",
        sampleName="SlicerMRClass1",
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, "SlicerMRClass1.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames="SlicerMRClass1.nrrd",
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums="SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        # This node name will be used when the data set is loaded
        nodeNames="SlicerMRClass1",
    )

    # SlicerMRClass2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="SlicerMRClass",
        sampleName="SlicerMRClass2",
        thumbnailFileName=os.path.join(iconsPath, "SlicerMRClass2.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames="SlicerMRClass2.nrrd",
        checksums="SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        # This node name will be used when the data set is loaded
        nodeNames="SlicerMRClass2",
    )


#
# SlicerMRClassParameterNode
#


@parameterNodeWrapper
class SlicerMRClassParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode


#
# SlicerMRClassWidget
#


class SlicerMRClassWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""

        #######################################
        ###### First download files needed ####
        ########################################

        def download_github_release_file(github_release_url, file_name, save_path):
            # Ensure the Resources directory exists
            os.makedirs(save_path, exist_ok=True)

            # Construct the full URL for the attachment
            download_url = f"{github_release_url}/assets/{file_name}"

            # Send the GET request to download the file
            response = requests.get(download_url, stream=True)
            if response.status_code == 200:
                file_path = os.path.join(save_path, file_name)
                with open(file_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"File downloaded and saved to {file_path}")
            else:
                print(f"Failed to download file: {response.status_code} - {response.text}")

        github_release_url = "https://github.com/deepakri201/DICOMScanClassification_pw42/releases/tag/v1.0.0"
        save_path = os.path.join(slicer.app.temporaryPath, "Resources") 
        # Download the scaling factors csv file
        file_name = "scaling_factors_df.csv"
        self.scaling_factors_filename = os.path.join(save_path, file_name) 
        download_github_release_file(github_release_url, file_name, save_path)
        # Download the model onnx file 
        file_name = "model.onnx"
        self.model_filename = os.path.join(save_path, file_name)
        download_github_release_file(github_release_url, file_name, save_path)

        #########################
        ### Setup AI packages ###
        #########################

        try: 
            import onnxruntime as onx 
        except: 
            progressDialog = slicer.util.createProgressDialog(labelText='Upgrading onnxruntime. This may take a minute...', maximum=0)
            slicer.app.processEvents()
            slicer.util.pip_install("onnxruntime")
            import onnxruntime as onx 
            progressDialog.close()

        ##############
        ### Set up ###
        ##############

        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/SlicerMRClass.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = SlicerMRClassLogic()

        ###################
        ### Connections ###
        ###################

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        # self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.runModelButton.connect("clicked(bool)", self.onRunModelButton)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

        # Add patients to list 
        self.addPatientsToList()

        # Detect which patient is selected 
        self.patientIDListGroupBox.connect("currentIndexChanged(int)", self.onPatientSelected)
        self.patientIDListGroupBox.setEnabled(True)

        # # Detect which study is selected 
        # self.studyIDListGroupBox.connect("currentIndexChanged(int)", self.onStudySelected)
        # self.studyIDListGroupBox.setEnabled(True)

        # set text 
        self.ui.ListPatientsLabel.setText("Choose a single patient")
        self.ui.ListStudiesLabel.setText("Choose a single study")
        self.ui.ListSeriesLabel.setText("List of series in the study")


    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[SlicerMRClassParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.inputVolume and self._parameterNode.thresholdedVolume:
            self.ui.applyButton.toolTip = _("Compute output volume")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input and output volume nodes")
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            self.logic.process(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
                               self.ui.imageThresholdSliderWidget.value, self.ui.invertOutputCheckBox.checked)

            # Compute inverted output (if needed)
            if self.ui.invertedOutputSelector.currentNode():
                # If additional output volume is selected then result with inverted threshold is written there
                self.logic.process(self.ui.inputSelector.currentNode(), self.ui.invertedOutputSelector.currentNode(),
                                   self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)
                
    def onRunModelButton(self) -> None:
        """Run processing when user clicks "Run Model" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to run model on series."), waitCursor=True):
            # # Compute output
            # self.logic.process(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
            #                    self.ui.imageThresholdSliderWidget.value, self.ui.invertOutputCheckBox.checked)

            # # Compute inverted output (if needed)
            # if self.ui.invertedOutputSelector.currentNode():
            #     # If additional output volume is selected then result with inverted threshold is written there
            #     self.logic.process(self.ui.inputSelector.currentNode(), self.ui.invertedOutputSelector.currentNode(),
            #                        self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)
            # self.onButtonLoadSeries()
            # self.onButtonGetImages()
            self.onButtonLoadSeries() 

    def onButtonLoadSeries(self): 
        # get each of the series
        db = slicer.dicomDatabase
        num_series = len(self.showSeriesIndex)
        for series in range(0,num_series):
            fileList = db.filesForSeries(series) 
            num_files = len(fileList)
            IPP = [] 
            for n in range(0,num_files): 
                IPP.append(db.fileValue(fileList[n], "0020,0032"))
            # sort files and get IPP and SOPInstanceUID of middle slice 
            IPP = [float(f) for f in IPP]
            IPP_index = np.argsort(IPP)
            # get middle IPP 
            midIPP_index = np.int32(np.floor(len(IPP_index)/2))
            # get the appropriate SOPInstanceUID for this particular series 
            midSOPInstanceUID = db.fileValue(fileList[midIPP_index], "0008,0018")
            # add to the seriesMap 
            self.seriesMap[series]['midSOPInstanceUID'] = midSOPInstanceUID

    def onButtonProcessSeriesData(self):
        # now load each of the series image data and get metadata, and process 
        db = slicer.dicomDatabase 
        num_series = len(self.showSeriesIndex) 
        for series in range(0,num_series): 
            dicom_file_path = db.fileForInstance(self.seriesMap[series]['midSOPInstanceUID']) 
            ds = pydicom.dcmread(dicom_file_path) 
            # get the image data 
            pixel_array = ds.pixel_array # need to reshape 
            # get the metadata 
            RepetitionTime = ds.RepetitionTime 
            EchoTime = ds.EchoTime 
            FlipAngle = ds.FlipAngle 
            scanningSequence = ds.ScanningSequence # EP\SE
            has_scanningSequence_SE = 0 
            has_scanningSequence_EP = 0 
            has_scanningSequence_GR = 0 
            if "SE" in scanningSequence: 
                has_scanningSequence_SE = 1 
            if "EP" in scanningSequence: 
                has_scanningSequence_EP = 1 
            if "GR" in scanningSequence: 
                has_scanningSequence_GR = 1 
            # process the 

          

   

    
    def listPatients(self):
        # list patients in DICOM database 
        db = slicer.dicomDatabase
        # this does not give the actual PatientID
        patientList = list(db.patients())
        # set up the patientMap
        patientMap = {} 
        for patient in patientList: 
            studyList = db.studiesForPatient(patient)
            seriesList = db.seriesForStudy(studyList[0]) 
            fileList = db.filesForSeries(seriesList[0])
            PatientID = db.fileValue(fileList[0], "0010,0020")
            patientMap[patient] = {'SlicerPatientID': patient}
            patientMap[patient]['PatientID'] = PatientID 
        self.patientMap = patientMap 

        # patientIDList = [] 
        # # get the actual PatientID
        # for patient in patientList: 
        #     studyList = db.studiesForPatient(patient)
        #     for study in studyList: 
        #         seriesList = db.seriesForStudy(study)
        #         fileList = db.filesForSeries(seriesList[0])
        #         # get PatientID 
        #         patientIDList.append(db.fileValue(fileList[0], "0010,0020"))
        # patientIDList = sorted(list(set(patientIDList)))  
        # return patientIDList 
    
    def listStudies(self): 
        # list studies for the patient selected 
        db = slicer.dicomDatabase
        # studyList = db.studiesForPatient(self.patientIDSelected)
        studyList = db.studiesForPatient(self.slicerPatientIDSelected) # returns the StudyInstanceUID 
        # set up the studyMap 
        studyMap = {} 
        for study in studyList: 
            seriesList = db.seriesForStudy(study) 
            fileList = db.filesForSeries(seriesList[0])
            StudyInstanceUID = study 
            StudyDate = db.fileValue(fileList[0], "0008,0020")
            StudyDescription = db.fileValue(fileList[0], "0008,1030")
            studyMap[study] = {'SlicerStudyID': study} 
            studyMap[study]['StudyInstanceUID'] = study 
            studyMap[study]['StudyDate'] = StudyDate 
            studyMap[study]['StudyDescription'] = StudyDescription
            studyMap[study]['StudyShortName'] = StudyDate + '_' + StudyDescription
        self.studyMap = studyMap 
        # print('studyList: ' + str(studyList))
        # return studyList 
    
    def listSeries(self): 
        db = slicer.dicomDatabase 
        # seriesList = db.seriesForStudy(self.study) # the study picked, returns the SeriesInstanceUID?? 
        seriesList = db.seriesForStudy(self.slicerStudyIDSelected)
        print("seriesList: " + str(seriesList)) # prints the SeriesInstanceUID 
        seriesMap = {} 
        for series in seriesList: 
            fileList = db.filesForSeries(series) 
            SeriesDescription = db.fileValue(fileList[0], "0008,103E")
            SeriesNumber = db.fileValue(fileList[0], "0020,0011")
            Modality = db.fileValue(fileList[0], "0008,0060")
            seriesMap[series] = {'SlicerSeriesID': series} 
            seriesMap[series]['SeriesInstanceUID'] = series 
            seriesMap[series]['SeriesNumber'] = SeriesNumber
            seriesMap[series]['SeriesDescription'] = SeriesDescription 
            seriesMap[series]['Modality'] = Modality 
        self.seriesMap = seriesMap 
        # print('seriesMap: ' + str(seriesMap)) # correct


    # def onPatientRadioButtonToggled(self, radiobutton, checked):
    #     if checked: 
    #         print(f"Selected Patient: {radiobutton.text}")
    #         # self.patientIDSelected = radiobutton.text
    #         # Instead of getting the PatientID, get the SlicerPatientID 
    #         # Create a reverse lookup dictionary
    #         patientIDToSlicerPatientID = {value['PatientID']: value['SlicerPatientID'] for key, value in self.patientMap.items()}
    #         # Lookup the SlicerPatientID
    #         slicerPatientID = patientIDToSlicerPatientID.get(radiobutton.text)
    #         self.slicerPatientIDSelected = slicerPatientID
    #         # add new studies to list 
    #         self.updateStudiesToList() 
    #     else:
    #         # self.patientIDSelected = ''
    #         self.slicerPatientIDSelected = ''

    # def onStudyRadioButtonToggled(self, radiobutton, checked):
    #     if checked: 
    #         print(f"Selected Study: {radiobutton.text}")
    #         # self.studyIDSelected = radiobutton.text
    #         # Instead of getting the StudyID, get the SlicerStudyID 
    #         # Create a reverse lookup dictionary
    #         studyIDToSlicerStudyID = {value['StudyShortName']: value['SlicerStudyID'] for key, value in self.studyMap.items()}
    #         # Lookup the SlicerPatientID
    #         slicerStudyID = studyIDToSlicerStudyID.get(radiobutton.text)
    #         self.slicerStudyIDSelected = slicerStudyID
    #     else:
    #         # self.patientIDSelected = ''
    #         self.slicerStudyIDSelected = ''
    
    # def addPatientIDs(self, patientIDs):
    #     # Clear existing widgets in the layout (if needed)
    #     while self.patientIDListLayout.count():
    #         child = self.patientIDListLayout.takeAt(0)
    #         if child.widget():
    #             child.widget().deleteLater()
    #     # Add each patient ID as a QRadioButton
    #     self.patientRadioButtons = [] 
    #     for patientID in patientIDs:
    #         # checkbox.stateChanged.connect(self.onCheckboxStateChanged)  # Connect state change
    #         radiobutton = qt.QRadioButton(patientID)
    #         radiobutton.toggled.connect(partial(self.onPatientRadioButtonToggled, radiobutton))
    #         self.patientIDListLayout.addWidget(radiobutton)
    #         self.patientRadioButtons.append(radiobutton)

    #     # Select the first patient by default
    #     if self.patientRadioButtons:
    #         self.patientRadioButtons[0].setChecked(True)

    # def addStudies(self, studies): 
    #     # Clear existing widgets in the layout (if needed)
    #     while self.studyListLayout.count():
    #         child = self.studyListLayout.takeAt(0)
    #         if child.widget():
    #             child.widget().deleteLater()
    #     # Add each study as a QRadioButton 
    #     self.studyRadioButtons = [] 
    #     for study in studies:
    #         radiobutton = qt.QRadioButton(study)
    #         radiobutton.toggled.connect(partial(self.onStudyRadioButtonToggled, radiobutton))
    #         self.studyListLayout.addWidget(radiobutton)
    #         self.studyRadioButtons.append(radiobutton)
        
    def addPatientIDs(self, patientIDs):
        # add patients to box
        self.patientIDListGroupBox.addItems(patientIDs)
        # set the selected patient to be the first one by default
        self.patientIDListGroupBox.setCurrentIndex(0)
        self.patient = self.patientIDListGroupBox.currentText 
        print('Selected patient: ' + str(self.patient))

    def addStudies(self, studies):
        # first clear 
        self.clearStudyIDListGroupBox() 
        # add studies to box 
        self.studyIDListGroupBox.addItems(studies)
        # set the selected study to be the first one by default 
        self.studyIDListGroupBox.setCurrentIndex(0) 
        self.study = self.studyIDListGroupBox.currentText 
        
    def onPatientSelected(self):
        currentText = self.patientIDListGroupBox.currentText
        # if empty 
        if currentText != "":
            self.patient = currentText
        # print out currently selected patient 
        print('Selected patient: ' + str(self.patient))
        # get the list of studies 
        self.patientIDSelected = self.patient 
        # Get the SlicerPatientID 
        # Create a reverse lookup dictionary
        patientIDToSlicerPatientID = {value['PatientID']: value['SlicerPatientID'] for key, value in self.patientMap.items()}
        # Lookup the SlicerPatientID
        slicerPatientID = patientIDToSlicerPatientID.get(self.patientIDSelected)
        self.slicerPatientIDSelected = slicerPatientID
        # add new studies to list 
        self.updateStudiesToList() 

        # Detect which study is selected 
        self.studyIDListGroupBox.connect("currentIndexChanged(int)", self.onStudySelected)
        self.studyIDListGroupBox.setEnabled(True)
       

    
    def onStudySelected(self):
        currentText = self.studyIDListGroupBox.currentText
        if currentText != "":
            self.study = currentText
        # print out currently selected study 
        print('Selected study: ' + str(self.study))
        # get the actual id 
        self.studyIDSelected = self.study 
        # Get the SlicerStudyID 
        # Create a reverse lookup dictionary 
        studyIDToSlicerStudyID = {value['StudyShortName']: value['SlicerStudyID'] for key, value in self.studyMap.items()}
        # Lookup the SlicerStudyID 
        slicerStudyID = studyIDToSlicerStudyID.get(self.studyIDSelected)
        self.slicerStudyIDSelected = slicerStudyID 
         # list series 
        self.addSeriesToList() 
        
    def addPatientsToList(self):
        self.patientIDListGroupBox = self.ui.PatientIDlist
        # Create and set a QVBoxLayout for the group box
        self.patientIDListLayout = qt.QVBoxLayout()
        self.patientIDListGroupBox.setLayout(self.patientIDListLayout)
        # Get the list of patients
        self.listPatients()
        patientIDList = [value['PatientID'] for key, value in self.patientMap.items()]
        # Add text to the layout
        self.addPatientIDs(patientIDList)
        # Set it so the first patient is automatically selected 
        self.patientIDListGroupBox.setCurrentIndex(0)

    # def addStudiesToList(self): 
    #     self.studyListGroupBox = self.ui.StudyIDlist 
    #     # Create and set a QVBoxLayout for the group box 
    #     self.studyListLayout = qt.QVBoxLayout() 
    #     self.studyListGroupBox.setLayout(self.studyListLayout) 
    #     # Get the list of studies 
    #     self.listStudies() 
    #     studyIDList = [value['StudyShortName'] for key, value in self.studyMap.items()]
    #     # Add text to the layout 
    #     self.addStudies(studyIDList)


    def updateStudiesToList(self): 
        self.studyIDListGroupBox = self.ui.StudyIDlist 
        # Get the existing layout of the StudyIDlist group box
        # layout = self.ui.StudyIDlist.layout()
        layout = self.studyIDListGroupBox.layout() 
        # If the layout doesn't exist, create one
        if layout is None:
            # layout = qt.QVBoxLayout(self.ui.StudyIDlist)
            # self.ui.StudyIDlist.setLayout(layout)
            self.studyIDListLayout = qt.QVBoxLayout() 
            self.studyIDListGroupBox.setLayout(self.studyIDListLayout) 
        # Clear existing widgets in the layout
        if layout is not None: 
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        self.listStudies()
        studyIDList = [value['StudyShortName'] for key, value in self.studyMap.items()]
        self.addStudies(studyIDList)

    def addSeriesToList(self): 
        # self.ListSeriesTable = self.ui.ListSeriesTable
        # list series 
        self.listSeries() 

        # get SeriesNumbers, SeriesDescriptions, Modalities 
        SeriesNumberList = [value['SeriesNumber'] for key, value in self.seriesMap.items()] 
        SeriesDescriptionList = [value['SeriesDescription'] for key,value in self.seriesMap.items()]
        ModalityList = [value['Modality'] for key,value in self.seriesMap.items()]

        # Order these lists according to the SeriesNumber 
        SeriesNumberList = [np.int16(f) for f in SeriesNumberList]
        order_index = np.argsort(np.asarray(SeriesNumberList))
        # np.array(X_train)[indices.astype(int)]
        SeriesNumberListSorted = np.array(SeriesNumberList)[order_index.astype(int)]
        SeriesNumberListSorted = [str(f) for f in SeriesNumberListSorted]
        SeriesDescriptionListSorted = np.array(SeriesDescriptionList)[order_index.astype(int)]
        ModalityListSorted = np.array(ModalityList)[order_index.astype(int)]

        # correct 
        print('SeriesNumberList: ' + str(SeriesNumberListSorted)) 
        print('SeriesDescriptionList: ' + str(SeriesDescriptionListSorted))
        print('ModalityList: ' + str(ModalityListSorted))

        # Create a list of 0/1s of these to indicate whether to show or grayed 
        self.showSeriesIndex =  [1 if modality == 'MR' else 0 for modality in ModalityList]
        print('showSeriesIndex: ' + str(self.showSeriesIndex))

        # first create QStandardItemModel 
        self.model = qt.QStandardItemModel() 
        self.model.setColumnCount(3) # SeriesNumber, SeriesDescription, Modality 
        headerNames = [] 
        headerNames.append("Modality")
        headerNames.append("SeriesNumber")
        headerNames.append("SeriesDescription")
        self.model.setHorizontalHeaderLabels(headerNames)

        # add series to list 
        for n in range(0,len(SeriesDescriptionListSorted)): 
            ModalityItem = qt.QStandardItem(ModalityListSorted[n]) 
            SeriesNumberItem = qt.QStandardItem(SeriesNumberListSorted[n]) 
            SeriesDescriptionItem = qt.QStandardItem(SeriesDescriptionListSorted[n])
            # Set certain ones to gray if Modality is not "MR"
            if self.showSeriesIndex[n]==0:
                ModalityItem.setForeground(qt.QColor("gray"))
                SeriesNumberItem.setForeground(qt.QColor("gray"))
                SeriesDescriptionItem.setForeground(qt.QColor("gray"))
            # Set to non editable 
            ModalityItem.setEditable(False) 
            SeriesNumberItem.setEditable(False) 
            SeriesDescriptionItem.setEditable(False)
            row = [] 
            row.append(ModalityItem)
            row.append(SeriesNumberItem) 
            row.append(SeriesDescriptionItem) 
            self.model.appendRow(row)

        # Now set the size of the columns - to be adjusted to length of text 
        # self.ui.ListSeriesTable.verticalHeader().setSectionResizeMode(qt.QHeaderView.ResizeToContents)
        
        # show 
        self.model.layoutChanged.emit() # need this? 
        self.ui.ListSeriesTable.setModel(self.model) 
        print('self.ui.ListSeriesTable.showGrid: ' + str(self.ui.ListSeriesTable.showGrid)) # should print True/False 
        self.ui.ListSeriesTable.setShowGrid(True)




    # def clearStudyIDListGroupBox(self):
    #     """Remove all items/widgets from the ctkGroupBox."""
    #     # while self.StudyIDListLayout.count():
    #     print("self.studyIDListGroupBox.layout().count()" + str(self.studyIDListGroupBox.layout().count()))
    #     while self.studyIDListGroupBox.layout().count(): 
    #         # child = self.StudyIDListLayout.takeAt(0)  # Remove the item at index 0
    #         child = self.StudyIDListGroupBox.layout().takeAt(0) 
    #         if child.widget():
    #             child.widget().deleteLater()  # Delete the widget
    
    
    def clearStudyIDListGroupBox(self): 
        # Remove all studies before repopulating 
        self.studyIDListGroupBox.clear()




#
# SlicerMRClassLogic
#


class SlicerMRClassLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return SlicerMRClassParameterNode(super().getParameterNode())

    def process(self,
                inputVolume: vtkMRMLScalarVolumeNode,
                outputVolume: vtkMRMLScalarVolumeNode,
                imageThreshold: float,
                invert: bool = False,
                showResult: bool = True) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        :param inputVolume: volume to be thresholded
        :param outputVolume: thresholding result
        :param imageThreshold: values above/below this threshold will be set to 0
        :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
        :param showResult: show output volume in slice viewers
        """

        if not inputVolume or not outputVolume:
            raise ValueError("Input or output volume is invalid")

        import time

        startTime = time.time()
        logging.info("Processing started")

        # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
        cliParams = {
            "InputVolume": inputVolume.GetID(),
            "OutputVolume": outputVolume.GetID(),
            "ThresholdValue": imageThreshold,
            "ThresholdType": "Above" if invert else "Below",
        }
        cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
        # We don't need the CLI module node anymore, remove it to not clutter the scene with it
        slicer.mrmlScene.RemoveNode(cliNode)

        stopTime = time.time()
        logging.info(f"Processing completed in {stopTime-startTime:.2f} seconds")



#
# SlicerMRClassTest
#


class SlicerMRClassTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_SlicerMRClass1()

    def test_SlicerMRClass1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData

        registerSampleData()
        inputVolume = SampleData.downloadSample("SlicerMRClass1")
        self.delayDisplay("Loaded test data set")

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = SlicerMRClassLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay("Test passed")
