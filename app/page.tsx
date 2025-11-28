import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import LoginForm from "./components/LoginForm";

export default async function Page() {
    const cookieStore = await cookies();
    const token = cookieStore.get("token");

    if (token) {
        redirect("/market");
    }

    return <LoginForm />;
}
