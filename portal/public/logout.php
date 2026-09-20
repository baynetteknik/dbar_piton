<?php
declare(strict_types=1);
require __DIR__ . '/../src/web.php';

web_session();
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    web_check_csrf();
    $_SESSION = [];
    session_destroy();
}
header('Location: login.php');
