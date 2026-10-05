import AuthLinksSection from "../components/auth/AuthLinksSection";
import AuthFormSection from "../components/auth/AuthFormSection";
import PageHeading from "../components/primitives/PageHeading";
import useForgotPasswordPage from "../components/auth/useForgotPasswordPage";

const ForgotPassword = () => {
  const page = useForgotPasswordPage();

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-center text-2xl font-bold sm:text-3xl"
      />
      <AuthFormSection
        mode="forgot"
        email={page.email}
        onEmailChange={page.setEmail}
        onSubmit={page.handleSubmit}
        busy={page.submitting}
        message={page.message}
        messageType={page.messageType}
        disabled={page.submitting}
      />
      <AuthLinksSection
        promptText="Remembered it?"
        linkTo="/login"
        linkLabel="Back to login"
      />
    </div>
  );
};

export default ForgotPassword;
