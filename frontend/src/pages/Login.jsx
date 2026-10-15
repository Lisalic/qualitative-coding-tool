import { Link } from "react-router-dom";
import AuthLinksSection from "../features/auth/AuthLinksSection";
import AuthFormSection from "../features/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useLoginPage from "../features/auth/useLoginPage";

const Login = () => {
  const page = useLoginPage();

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-center text-2xl font-bold sm:text-3xl"
      />
      <AuthFormSection
        mode="login"
        email={page.email}
        password={page.password}
        onEmailChange={page.setEmail}
        onPasswordChange={page.setPassword}
        onSubmit={page.handleSubmit}
        busy={page.submitting}
        message={page.message}
        messageType={page.messageType}
      />
      <Link
        to="/forgot-password"
        className="text-sm text-paper underline underline-offset-2 hover:text-paper/70"
      >
        Forgot password?
      </Link>
      <AuthLinksSection
        promptText="Don't have an account?"
        linkTo="/register"
        linkLabel="Register here"
      />
    </div>
  );
};

export default Login;
