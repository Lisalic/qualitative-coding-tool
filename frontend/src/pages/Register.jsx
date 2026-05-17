import "../styles/Auth.css";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useRegisterPage from "../components/auth/useRegisterPage";

const Register = () => {
  const page = useRegisterPage();

  return (
    <div className="auth-container">
      <PageHeading title="Qualitative Coding Tool" className="auth-title" />
      <AuthFormSection
        mode="register"
        email={page.email}
        password={page.password}
        confirmPassword={page.confirmPassword}
        onEmailChange={page.setEmail}
        onPasswordChange={page.setPassword}
        onConfirmPasswordChange={page.setConfirmPassword}
        onSubmit={page.handleSubmit}
      />
      <AuthLinksSection
        promptText="Already have an account?"
        linkTo="/login"
        linkLabel="Login here"
      />
      <ErrorDisplay message={page.message} type={page.messageType} variant="message" />
    </div>
  );
};

export default Register;
