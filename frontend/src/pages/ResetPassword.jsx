import ErrorDisplay from "../components/feedback/ErrorDisplay";
import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useResetPasswordPage from "../components/auth/useResetPasswordPage";

const ResetPassword = () => {
  const page = useResetPasswordPage();

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-center text-2xl font-bold sm:text-3xl"
      />
      <AuthFormSection
        mode="reset"
        password={page.password}
        confirmPassword={page.confirmPassword}
        onPasswordChange={page.setPassword}
        onConfirmPasswordChange={page.setConfirmPassword}
        onSubmit={page.handleSubmit}
        disabled={page.submitting || !page.token}
      />
      <AuthLinksSection
        promptText="Link expired?"
        linkTo="/forgot-password"
        linkLabel="Request a new one"
      />
      <ErrorDisplay message={page.message} type={page.messageType} variant="message" />
    </div>
  );
};

export default ResetPassword;
