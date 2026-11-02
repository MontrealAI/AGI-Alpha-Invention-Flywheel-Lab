import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from optics import response

root = Path(__file__).resolve().parent
r = json.loads((root/"results/RESULTS.json").read_text())
fig,axes = plt.subplots(1,2,figsize=(11,3.7),layout="constrained")
w = np.linspace(.8,1.06,301)
d = np.asarray(r["K1"]["thickness_um"])
a = response(d,["MgF2","Ta2O5"],w,30,"s")
b = response([],[],w,30,"s")
axes[0].plot(w,a["T"],label="Constructed K1")
axes[0].plot(w,b["T"],label="Bare silica",linestyle="--")
axes[0].set(title="K1: useful transmission",xlabel="Wavelength (µm)",ylabel="Power fraction",ylim=(.90,1.005))
t = r["K2"][0]
d = np.asarray(t["arms"]["retained_procedure"]["thickness_um"])
w = np.linspace(.8,1.49,501)
a = response(d,["Ta2O5","SiO2"]*6,w,30,"s")
worst = min(t["manufacturing_and_angle_distribution_shift"]["cases"],key=lambda x:min(x["mean_pass_transmission"],x["mean_stop_reflection"]))
b = response(d*(1+worst["thickness_relative_shift"]),["Ta2O5","SiO2"]*6,w,worst["angle_deg"],worst["polarization"])
axes[1].plot(w,a["T"],label="Nominal transmission")
axes[1].plot(w,a["R"],label="Nominal reflection")
axes[1].plot(w,b["R"],label="Worst shift: reflection",linestyle="--")
axes[1].axvspan(.8,1.0,color="#4a9c84",alpha=.08)
axes[1].axvspan(1.24,1.49,color="#8e70c4",alpha=.08)
axes[1].set(title="K2: spectral routing; finite scope",xlabel="Wavelength (µm)",ylabel="Power fraction",ylim=(0,1.02))
for ax in axes:
    ax.grid(alpha=.2);ax.legend(fontsize=8,loc="best")
fig.savefig(root/"results/spectra.svg")
