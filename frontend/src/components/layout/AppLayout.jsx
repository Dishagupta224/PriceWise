import { Outlet } from "react-router-dom";
import OnboardingTour from "../OnboardingTour";
import HeaderBar from "./HeaderBar";
import SidebarNav from "./SidebarNav";

function AppLayout() {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_minmax(0,1fr)]">
      <SidebarNav />
      <div className="min-w-0">
        <HeaderBar />
        <OnboardingTour />
        <main className="px-4 pb-8 pt-4 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppLayout;
