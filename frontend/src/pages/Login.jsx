import "../styles/Auth.css";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useLoginPage from "../components/auth/useLoginPage";

const Login = () => {
  const page = useLoginPage();

  return (
    <div className="auth-container">
      <PageHeading title="Qualitative Coding Tool" className="auth-title" />
      <AuthFormSection
        mode="login"
        email={page.email}
        password={page.password}
        onEmailChange={page.setEmail}
        onPasswordChange={page.setPassword}
        onSubmit={page.handleSubmit}
      />
      <AuthLinksSection
        promptText="Don't have an account?"
        linkTo="/register"
        linkLabel="Register here"
      />
      <ErrorDisplay message={page.message} type={page.messageType} variant="message" />
    </div>
  );
};

export default Login;
