import ErrorDisplay from "../components/feedback/ErrorDisplay";
import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useLoginPage from "../components/auth/useLoginPage";

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
