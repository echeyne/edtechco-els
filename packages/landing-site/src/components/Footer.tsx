export default function Footer() {
  return (
    <footer className="border-t border-border py-8">
      <div className="container text-center">
        <p className="text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} EdTech Co. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
