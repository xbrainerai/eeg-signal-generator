import streamlit as st, subprocess, os, yaml
st.title("EEG Generator Control")
cfg = {"channels": st.slider("Channels", 1,32,8),
       "rate":     st.selectbox("Rate", [128,256,512,1024]),
       "mode":     st.selectbox("Mode", ["sine","noise","mixed"]),
       "artifacts": st.checkbox("Artifacts", True) }
if st.button("Start Stream"):
    with open("stream_config.yaml","w") as f: yaml.safe_dump(cfg,f)
    subprocess.Popen(["python","mock_eeg_stream.py"])
    st.success("Generator started ✔")
