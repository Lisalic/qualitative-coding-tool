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
    }, {})
  );

  useEffect(() => {
    setFormData(
      fields.reduce((acc, field) => {
        acc[field.id] = field.value || "";
        return acc;
      }, {})
    );
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
    }
    handleInputChange(field.id, value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (onSubmit) {
      await onSubmit(formData);
    }
  };

  const renderField = (field) => {
    const value = formData[field.id];
    const commonProps = {
      id: field.id,
      value,
      onChange: (e) => handleFieldChange(field, e.target.value),
      placeholder: field.placeholder,
      className: "form-input",
      disabled: submitButton?.disabled,
    };

    switch (field.type) {
      case "select":
        return (
          <select {...commonProps}>
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
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
                  className="radio-option"
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
      default:
        return <input {...commonProps} type={field.type || "text"} />;
    }
  };

  return (
    <div className="form-wrapper">
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
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <label htmlFor={field.id}>{field.label}</label>
                {field.extraButtons && Array.isArray(field.extraButtons)
                  ? field.extraButtons.map((b, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={b.onClick}
                        className={b.className || "load-prompt-btn"}
                        disabled={submitButton?.disabled}
                      >
                        {b.label}
                      </button>
                    ))
                  : field.extraButton && (
                      <button
                        type="button"
                        onClick={field.extraButton.onClick}
                        className={
                          field.extraButton.className || "load-prompt-btn"
                        }
                        disabled={submitButton?.disabled}
                      >
                        {field.extraButton.label}
                      </button>
                    )}
              </div>
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
