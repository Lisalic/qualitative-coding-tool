const VALID_TYPES = new Set(["success", "error", "info"]);

class ToastServiceImpl {
  show(message, type = "info") {
    const text = String(message ?? "");
    const normalizedType = VALID_TYPES.has(type) ? type : "info";
    const event = new CustomEvent("toast-show", {
      detail: { message: text, type: normalizedType },
    });
    window.dispatchEvent(event);
    window.alert(text);
  }

  confirm(message) {
    return Promise.resolve(window.confirm(String(message ?? "")));
  }
}

const ToastService = new ToastServiceImpl();

export default ToastService;
