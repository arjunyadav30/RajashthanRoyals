import { useEffect } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import GuidePage from "./pages/GuidePage";
import RankingsPage from "./pages/RankingsPage";
import TeamsPage from "./pages/TeamsPage";
import TeamProfilePage from "./pages/TeamProfilePage";
import PlayerPage from "./pages/PlayerPage";
import AvailabilityPage from "./pages/AvailabilityPage";
import RRFitPage from "./pages/RRFitPage";
import AuctionBoardPage from "./pages/AuctionBoardPage";
import StatsExplorerPage from "./pages/StatsExplorerPage";
import RecentFormPage from "./pages/RecentFormPage";
import DataMethodsPage from "./pages/DataMethodsPage";
import AllPlayersPage from "./pages/AllPlayersPage";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  return null;
}

function NotFound() {
  return (
    <div className="card mx-auto max-w-xl p-8 text-center">
      <p className="text-5xl font-black text-rr-600 dark:text-rr-400">404</p>
      <h1 className="mt-3 text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        That route does not exist in the Stage 1 build.
      </p>
      <Link to="/" className="btn-primary mt-5">
        Back to start
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<GuidePage />} />
          <Route path="overview" element={<Overview />} />
          <Route path="batters" element={<RankingsPage key="batter" role="batter" />} />
          <Route path="bowlers" element={<RankingsPage key="bowler" role="bowler" />} />
          <Route path="player/:role/:playerId" element={<PlayerPage />} />
          <Route path="recent-form/:playerId" element={<RecentFormPage />} />
          <Route path="stats-explorer" element={<StatsExplorerPage />} />
          <Route path="players" element={<AllPlayersPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="teams/:slug" element={<TeamProfilePage />} />
          <Route path="methods" element={<DataMethodsPage />} />
          <Route path="availability" element={<AvailabilityPage />} />
          <Route path="rr-fit" element={<RRFitPage />} />
          <Route path="auction-board" element={<AuctionBoardPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </>
  );
}
