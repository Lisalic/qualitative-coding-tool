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

  const handleSubmit = async (e) => {
    e.preventDefault();
    await onSubmit(formData);
  };

  const renderField = (field) => {
    const value = formData[field.id];
    const commonProps = {
      id: field.id,
      value,
      onChange: (e) => handleInputChange(field.id, e.target.value),
      placeholder: field.placeholder,
      className: "form-input",
      disabled: submitButton.disabled,
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
      case "textarea":
        return <textarea {...commonProps} rows={field.rows || 4} />;
      case "password":
        return <input {...commonProps} type="password" />;
      default:
        return <input {...commonProps} type={field.type || "text"} />;
    }
  };

  return (
    <div className="form-wrapper">
      <form onSubmit={handleSubmit} className="action-form">
        {fields.map((field) => (
          <div key={field.id} className="form-group">
            <label htmlFor={field.id}>{field.label}</label>
            {renderField(field)}
          </div>
        ))}

        <button
          type="submit"
          disabled={submitButton.disabled}
          className="btn btn-primary"
        >
          {submitButton.disabled ? submitButton.loadingText : submitButton.text}
        </button>
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
