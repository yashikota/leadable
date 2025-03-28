import { GithubIcon } from "lucide-react";
import { Link } from "react-router";

export function Navbar() {
  return (
    <div className="navbar bg-base-200 shadow-md">
      <div className="navbar-start flex items-center">
        <Link to="/" className="flex items-center gap-2">
          <img src="/icon.png" alt="Leadable" className="h-8 w-auto" />
          <span className="text-2xl font-semibold">Leadable</span>
        </Link>
      </div>
      <div className="navbar-end">
        <a
          href="https://github.com/yashikota/leadable"
          target="_blank"
          className="btn btn-outline border-none"
          rel="noreferrer"
          aria-label="GitHub"
        >
          <GithubIcon />
        </a>
      </div>
    </div>
  );
}
