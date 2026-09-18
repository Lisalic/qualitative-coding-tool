import ErrorDisplay from "../components/feedback/ErrorDisplay";
import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useRegisterPage from "../components/auth/useRegisterPage";

const Register = () => {
  const page = useRegisterPage();

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-center text-2xl font-bold sm:text-3xl"
      />
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
