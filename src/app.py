
import tensorflow as tf
import numpy as np
import plotly.graph_objects as go
import cv2 # included in module: opencv-python

import google.generativeai as genai
import PIL.Image
import os
from dotenv import load_dotenv

load_dotenv();
# tell collab to create the tile with the output of this cell

import google.generativeai as genai
import os
import streamlit as st

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Flatten
from tensorflow.keras.optimizers import Adamax
from tensorflow.keras.metrics import Precision, Recall

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

output_dir = 'saliency_maps'
os.makedirs(output_dir, exist_ok=True)

# this is a multimodal prompt. it has a text body and an image attachment
# tips to improve prompt
# - guide for a shorter or more sturctured output
# - tell it to think step-by-step (and verify each step)
# - get an llm to create a prompt
# - play with different roles (medical specialty)
def generate_explanation(img_path, model_prediction, confidence):
    prompt = f"""You are an expert neurologist. You are tasked with explaining a saliency map of a brain tumor MRI scan.
    The saliency map was generated by a deep learning model that was trained to classify brain tumors
    as either glioma, meningioma, pituitary, or no tumor.

    The saliency map highlights the regions of the image that the machine learning model is focusing on to make the prediction.

    The deep learning model predicted the image to be of class '{model_prediction}' with a confidence of {confidence * 100}%.

    In your response:
    - Explain what regions of the brain the model is focusing on, based on the saliency map. Refer to the regions highlighted
    in light cyan, those are the regions where the model is focusing on.
    - Explain possible reasons why the model made the prediction it did.
    - Don't mention anything like 'The saliency map highlights the regions the model is focusing on, which are in light cyan'
    in your explanation.
    - Keep your explanation to 4 sentences max.
    """

    img = PIL.Image.open(img_path)

    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content([prompt, img])

    return response.text

def generate_saliency_map(model, img_array, class_index, img_size):
    """
    Creates a visual representation (saliency map) highlighting areas of a brain MRI image that are most important for the model's prediction. Thus, enhancing transparency and trust in the output.
    """

    # Compute gradients of the target class with respect to the input image
    with tf.GradientTape() as tape:
        img_tensor = tf.convert_to_tensor(img_array)
        tape.watch(img_tensor)
        predictions = model(img_tensor)
        target_class = predictions[:, class_index]

    # Gradient processing
    gradients = tape.gradient(target_class, img_tensor)
    gradients = tf.math.abs(gradients)
    gradients = tf.reduce_max(gradients, axis=-1)
    gradients = gradients.numpy().squeeze()

    # Resize gradients to match original image size
    gradients = cv2.resize(gradients, img_size)

    # Create a circular mask for the brain area
    center = (gradients.shape[0] // 2, gradients.shape[1] // 2)
    radius = min(center[0], center[1]) - 10
    y, x = np.ogrid[:gradients.shape[0], :gradients.shape[1]]
    mask = (x - center[0])**2 + (y - center[1])**2 <= radius**2

    # Apply mask to gradients
    gradients = gradients * mask

    # Normalize only the brain area
    brain_gradients = gradients[mask]
    if brain_gradients.max() > brain_gradients.min():
        brain_gradients = (brain_gradients - brain_gradients.min()) / (brain_gradients.max() - brain_gradients.min())
    gradients[mask] = brain_gradients

    # Apply a higher threshold
    threshold = np.percentile(gradients[mask], 80)
    gradients[gradients < threshold] = 0

    # Apply more aggressive smoothing
    gradients = cv2.GaussianBlur(gradients, (11, 11), 0)

    # Create a heatmap overlay with enhanced contrast
    heatmap = cv2.applyColorMap(np.uint8(255 * gradients), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    # Resize heatmap to match original image size
    heatmap = cv2.resize(heatmap, img_size)

    # Superimpose the heatmap on original image with increased opacity
    original_img = image.img_to_array(img)
    superimposed_img = heatmap * 0.7 + original_img * 0.3
    superimposed_img = superimposed_img.astype(np.uint8)

    # Save the original uploaded image
    img_path = os.path.join(output_dir, uploaded_file.name)
    with open(img_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Define path and save the saliency map
    saliency_map_path = f'saliency_maps/{uploaded_file.name}'
    cv2.imwrite(saliency_map_path, cv2.cvtColor(superimposed_img, cv2.COLOR_RGB2BGR))

    return superimposed_img

def load_transfered_model(model_name, model_path, img_size):
    img_shape=(img_size,img_size,3)
    if model_name == "Xception":
        base_model = tf.keras.applications.Xception(include_top=False, weights="imagenet",
                                                  input_shape=img_shape, pooling='max')
    elif model_name == "EfficientNetB3":
        base_model = tf.keras.applications.EfficientNetB3(include_top=False, weights="imagenet",
                                                  input_shape=img_shape, pooling='max')

    model = Sequential([
        base_model,
        Flatten(),
        Dropout(rate=0.3),
        Dense(128, activation='relu'),
        Dropout(rate=0.25),
        Dense(4, activation='softmax')
    ])

    model.build((None,) + img_shape)

    # Compile the model
    model.compile(Adamax(learning_rate=0.001),
                 loss='categorical_crossentropy',
                 metrics=['accuracy',
                         Precision(),
                         Recall()])

    model.load_weights(model_path)

    return model

def img_data_prep(img):
    """
    Image Data Preparation: convert to array, normalize and expand dimensions
    """
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) # convert image to an array
    img_array /= 255.0 # normalization
    return img_array

def get_predictions(img_array):
    """
    Get predictions from the model
    """
    prediction = model.predict(img_array)
    return prediction        

# BUILD UI
st.title("Brain Tumor Classification")
st.write("Upload an image of a brain MRI scan to classify.")

uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:

    # SELECT A PREDICTION MODEL
    selected_model = st.radio(
        "Select Model",
        ("Transfer Learning - Xception", "Transfer Learning - EfficientNetB3", "CNN 1M-Parameters", "CNN 4M7-Parameters")
    )

    models_folder_path = os.path.abspath(os.path.join(os.path.dirname("app.py"), '..', 'models'))
    if selected_model == "Transfer Learning - Xception":
        model = load_transfered_model('Xception', os.path.join(models_folder_path, 'xception_model.weights.h5'), 299)
        img_size = (299, 299)
    elif selected_model == "Transfer Learning - EfficientNetB3":
        model = load_transfered_model('EfficientNetB3', os.path.join(models_folder_path, 'efficientnet_model.weights.h5'), 300)
        img_size = (300, 300)
    elif selected_model == "CNN 1M-Parameters":
        model = load_model(os.path.join(models_folder_path, 'cnn_model_1M0.h5'))
        img_size = (224, 224)
    else:
        model = load_model(os.path.join(models_folder_path, 'cnn_model_4M7.h5'))
        img_size = (224, 224)

    # LIST PREDICTIONS
    labels = ['Glioma', 'Meningioma', 'No tumor', 'Pituitary']

    img = image.load_img(uploaded_file, target_size=img_size)
    img_array = img_data_prep(img)
    predictions = get_predictions(img_array)

    # Get the class with the highest probability
    class_index = np.argmax(predictions[0])
    result = labels[class_index]

    # st.write(f"Predicted Class: {result}")
    # st.write("Predictions:")
    # for label, prob in zip(labels, predictions[0]):
    #     st.write(f"{label}: {prob:.4f}")

    class_index = np.argmax(predictions[0])
    result = labels[class_index]

    st.write("## Classification Results")

    result_container = st.container()
    result_container = st.container()

    result_container.markdown(f"""
    <div style="background-color: #000000; color: #ffffff; padding: 30px; border-radius: 15px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="flex: 1; text-align: center;">
                <h3 style="color: #ffffff; margin-bottom: 10px; font-size: 20px;">Prediction</h3>
                <p style="font-size: 36px; font-weight: 800; color: #FF0000; margin: 0;">{result}</p>
            </div>
            <div style="width: 2px; height: 80px; background-color: #ffffff; margin: 0 20px;"></div>
            <div style="flex: 1; text-align: center;">
                <h3 style="color: #ffffff; margin-bottom: 10px; font-size: 20px;">Confidence</h3>
                <p style="font-size: 36px; font-weight: 800; color: #2196F3; margin: 0;">{predictions[0][class_index]:.4%}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Prepare data for Plotly chart
    probabilities = predictions[0]
    sorted_indices = np.argsort(probabilities)[::-1]
    sorted_labels = [labels[i] for i in sorted_indices]
    sorted_probabilities = probabilities[sorted_indices]

    # Create a Plotly bar chart
    fig = go.Figure(go.Bar(
        x=sorted_probabilities,
        y=sorted_labels,
        orientation='h',
        marker_color=['red' if label == result else 'blue' for label in sorted_labels]
    ))

    # Customize the chart layout
    fig.update_layout(
        title='Probabilities for each class',
        xaxis_title='Probability',
        yaxis_title='Class',
        height=400,
        width=600,
        yaxis=dict(autorange="reversed")
    )

    # Add value labels to the bars
    for i, prob in enumerate(sorted_probabilities):
        fig.add_annotation(
            x=prob,
            y=i,
            text=f'{prob:.4f}',
            showarrow=False,
            xanchor='left',
            xshift=5
        )

    st.plotly_chart(fig)

    saliency_map = generate_saliency_map(model, img_array, class_index, img_size)
    saliency_map_path = f'saliency_maps/{uploaded_file.name}'
    explanation = generate_explanation(saliency_map_path, result, predictions[0][class_index])

    st.write("## Explanation")
    st.write(explanation)
    with st.expander("MRI Scan Image - Saliency Map"):
        col1, col2 = st.columns(2)
        with col1:
            st.image(uploaded_file, caption='Uploaded Image', use_container_width=True)
        with col2:
            st.image(saliency_map,
                    caption='Saliency Map',
                    use_container_width=True)
        
