import { useState, useEffect } from "react";
import "../styles/Home.css";

export default function ActionForm({
  fields,
  submitButton,
  onSubmit,
  error,
  result,
  resultTitle,
}) {
  const [formData, setFormData] = useState(
    fields.reduce((acc, field) => {
      acc[field.id] = field.value || "";
      return acc;
    }, {}),
  );

  useEffect(() => {
    // Merge incoming field defaults into existing form data instead of
    // replacing it outright. This avoids losing user edits when the parent
    // recreates the `fields` array on every render.
    setFormData((prev) => {
      const merged = { ...prev };
      fields.forEach((field) => {
        if (field.onChange) {
          merged[field.id] = field.value || "";
        } else if (merged[field.id] === undefined) {
          merged[field.id] = field.value || "";
        }
      });
      return merged;
    });
  }, [fields]);

  const handleInputChange = (fieldId, value) => {
    setFormData((prev) => ({
      ...prev,
      [fieldId]: value,
    }));
  };

  const handleFieldChange = (field, value) => {
    if (field.onChange) {
      field.onChange(value);
    } else {
      handleInputChange(field.id, value);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!onSubmit) return;
    const finalFormData = { ...formData };
    fields.forEach((field) => {
      if (field.onChange) {
        finalFormData[field.id] = field.value;
      }
    });
    await onSubmit(finalFormData);
  };

  const renderField = (field) => {
    const value = field.onChange ? field.value : formData[field.id];
    const commonProps = {
      id: field.id,
      value,
      onChange: (e) => handleFieldChange(field, e.target.value),
      placeholder: field.placeholder,
      className: "form-input",
      disabled: submitButton?.disabled,
    };

    switch (field.type) {
      case "select": {
        let placeholderText =
          field.placeholder ||
          `Select a ${field.label.toLowerCase().replace(/^select\s+/i, "")}`;
        if (
          field.id === "model" ||
          field.label.toLowerCase().includes("ai model")
        ) {
          placeholderText = "Select an AI model";
        }
        return (
          <select {...commonProps}>
            {!value && (
              <option value="" disabled>
                {placeholderText}
              </option>
            )}
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      }
      case "radio":
        return (
          <div className="radio-group">
            {field.options.map((option) => (
              <div key={option.value}>
                <input
                  type="radio"
                  id={`${field.id}-${option.value}`}
                  name={field.id}
                  value={option.value}
                  checked={value === option.value}
                  onChange={(e) => handleFieldChange(field, e.target.value)}
                  disabled={submitButton?.disabled}
                  style={{ display: "none" }}
                />
                <label
                  htmlFor={`${field.id}-${option.value}`}
                  className="radio-label"
                >
                  {option.label}
                </label>
              </div>
            ))}
          </div>
        );
      case "textarea":
        return <textarea {...commonProps} rows={field.rows || 4} />;
      case "password":
        return <input {...commonProps} type="password" />;
      case "button":
        return (
          <button type="button" onClick={field.onClick} className="view-button">
            {field.label}
          </button>
        );
      case "title":
        return <h1>{field.label}</h1>;
      case "custom":
        return field.render ? field.render() : null;
      default:
        return <input {...commonProps} type={field.type || "text"} />;
    }
  };

  return (
    <div className="action-form-wrapper">
      <form onSubmit={handleSubmit} className="action-form">
        {fields.map((field) => {
          if (field.type === "title") {
            return <div key={field.id}>{renderField(field)}</div>;
          }
          if (field.type === "button") {
            return (
              <div key={field.id} className="action-buttons">
                {renderField(field)}
              </div>
            );
          }
          return (
            <div key={field.id} className="form-group">
              <label htmlFor={field.id}>{field.label}</label>
              {field.extraButtons && Array.isArray(field.extraButtons) ? (
                <div style={{ textAlign: "right", marginTop: "-2rem" }}>
                  {field.extraButtons.map((b, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={b.onClick}
                      className={b.className || "load-prompt-btn"}
                      disabled={submitButton?.disabled}
                      style={{ marginLeft: "0.5rem" }}
                    >
                      {b.label}
                    </button>
                  ))}
                </div>
              ) : field.extraButton ? (
                <div style={{ textAlign: "right", marginTop: "-2rem" }}>
                  <button
                    type="button"
                    onClick={field.extraButton.onClick}
                    className={field.extraButton.className || "load-prompt-btn"}
                    disabled={submitButton?.disabled}
                  >
                    {field.extraButton.label}
                  </button>
                </div>
              ) : null}
              {renderField(field)}
            </div>
          );
        })}

        {submitButton && (
          <button
            type="submit"
            disabled={submitButton.disabled}
            className="form-submit-btn"
          >
            {submitButton.disabled
              ? submitButton.loadingText
              : submitButton.text}
          </button>
        )}
      </form>

      {error && <p className="form-message">{error}</p>}

      {result && (
        <div className="result">
          <h2>{resultTitle}</h2>
          <pre>
            {typeof result === "string"
              ? result
              : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
