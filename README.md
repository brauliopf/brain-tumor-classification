Train machine learning models to classify brain tumors from MRI scans.
The application uses different prediction models, based on NN, to diagnose from the images provided. In addition to that, the application engages a multi-modal LLM (`gemini-1.5-flash` through `google.generativeai` module) to understand and explain the model's predictions.

Train and compare the outputs of 4 different deep learning models: 2 leverging an existing model through transfer learning (xception and EfficientNetB3); and other 2 models created from a custom convolutional neural network with 4 layers and 1.7.
Create a webapp with streamlit to generate predictions usign the models generated in part 1; visualize which areas of the scans are important to reach the predictions; and provide an explanation for the conclusions based on the observations from the MRI scan.
Furthermore, the application suggests relevant actions to add to a patient's care plan in the short-term.

The app is available at: https://brain-tumor-classification-brauliopf.streamlit.app/

Contributors:
@brauliopf
@headstarter

NEW CHANGE
NEW CHANGE 2
