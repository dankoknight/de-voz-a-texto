(() => {
  const fileInput = document.getElementById("file-input");
  const dropzone = document.getElementById("dropzone");
  const fileNameEl = document.getElementById("file-name");
  const languageEl = document.getElementById("language");
  const btnTranscribe = document.getElementById("btn-transcribe");
  const engineInfo = document.getElementById("engine-info");
  const progressPanel = document.getElementById("progress-panel");
  const barFill = document.getElementById("bar-fill");
  const progressMsg = document.getElementById("progress-msg");
  const resultPanel = document.getElementById("result-panel");
  const transcript = document.getElementById("transcript");
  const btnCopy = document.getElementById("btn-copy");
  const btnDownload = document.getElementById("btn-download");
  const toast = document.getElementById("toast");

  let selectedFile = null;
  let pollTimer = null;

  async function loadHealth() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      const engine =
        data.engine === "openai"
          ? "OpenAI Whisper (API)"
          : `Whisper local (${data.model}, ${data.device})`;
      engineInfo.textContent = `Motor: ${engine} · Idioma por defecto: ${data.default_language}`;
    } catch {
      engineInfo.textContent = "No se pudo consultar el estado del motor.";
    }
  }

  function setFile(file) {
    selectedFile = file || null;
    btnTranscribe.disabled = !selectedFile;
    if (selectedFile) {
      fileNameEl.hidden = false;
      fileNameEl.textContent = `Archivo: ${selectedFile.name} (${formatBytes(selectedFile.size)})`;
    } else {
      fileNameEl.hidden = true;
      fileNameEl.textContent = "";
    }
  }

  function formatBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }

  function showToast(msg) {
    toast.hidden = false;
    toast.textContent = msg;
    setTimeout(() => {
      toast.hidden = true;
    }, 2200);
  }

  function setProgress(pct, msg) {
    progressPanel.hidden = false;
    barFill.style.width = `${pct}%`;
    progressPanel.querySelector(".bar").setAttribute("aria-valuenow", String(pct));
    progressMsg.textContent = msg;
  }

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const file = e.dataTransfer.files?.[0];
    if (file) {
      fileInput.files = e.dataTransfer.files;
      setFile(file);
    }
  });
  fileInput.addEventListener("change", () => setFile(fileInput.files?.[0] || null));

  btnTranscribe.addEventListener("click", async () => {
    if (!selectedFile) return;
    btnTranscribe.disabled = true;
    resultPanel.hidden = true;
    transcript.value = "";
    setProgress(8, "Subiendo audio…");

    const form = new FormData();
    form.append("file", selectedFile);
    form.append("language", languageEl.value);

    try {
      const res = await fetch("/api/transcribe", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "No se pudo iniciar la transcripción");
      }
      const { job_id } = await res.json();
      pollJob(job_id);
    } catch (err) {
      setProgress(100, err.message || "Error");
      btnTranscribe.disabled = !selectedFile;
    }
  });

  function pollJob(jobId) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) throw new Error("Trabajo no encontrado");
        const job = await res.json();
        setProgress(job.progress || 0, job.message || "Procesando…");

        if (job.status === "done") {
          clearInterval(pollTimer);
          transcript.value = job.text || "";
          resultPanel.hidden = false;
          btnTranscribe.disabled = !selectedFile;
          setProgress(100, "Listo");
        } else if (job.status === "error") {
          clearInterval(pollTimer);
          setProgress(100, job.error || "Error al transcribir");
          btnTranscribe.disabled = !selectedFile;
        }
      } catch (err) {
        clearInterval(pollTimer);
        setProgress(100, err.message || "Error de seguimiento");
        btnTranscribe.disabled = !selectedFile;
      }
    }, 700);
  }

  btnCopy.addEventListener("click", async () => {
    const text = transcript.value;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showToast("Copiado al portapapeles");
    } catch {
      transcript.select();
      document.execCommand("copy");
      showToast("Copiado");
    }
  });

  btnDownload.addEventListener("click", () => {
    const text = transcript.value;
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcripcion.txt";
    a.click();
    URL.revokeObjectURL(url);
    showToast("Descarga iniciada");
  });

  loadHealth();
})();
